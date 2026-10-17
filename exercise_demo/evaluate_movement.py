"""Cache pose extraction, then evaluate ordered movement and existing image baseline.
Development and holdout folder selections are fixed before evaluation. They are not
proven participant-disjoint. No phone accuracy claim follows from these results.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from time import perf_counter
import cv2
import numpy as np
from PIL import Image
from movement import PoseEstimator, MovementRecognizer, Features

ROOT=Path(__file__).resolve().parent

def stable_labels(labels):
    return [label if i>=2 and labels[i-2:i+1]==[label]*3 else 'unknown' for i,label in enumerate(labels)]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['development','holdout','final'],default='development')
    parser.add_argument('--image-baseline',action='store_true')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'data/motion/manifest.json').read_text())
    pose=PoseEstimator();image_model=None
    if args.image_baseline:
        from classifier import ExerciseClassifier
        image_model=ExerciseClassifier()
    rows=[];all_times=[]
    for clip in manifest['clips']:
        if clip['split']!=args.split:continue
        path=ROOT/'data/motion'/clip['path']
        key=hashlib.sha256((clip['sha256']+'pose-full-v1-vis06-8hz').encode()).hexdigest()
        cache=ROOT/'data/motion/features'/f'{key}.json';cache.parent.mkdir(exist_ok=True)
        if cache.exists():frames=json.loads(cache.read_text())
        else:
            cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);total=cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if fps<=0 or total<=0:raise RuntimeError(f'Cannot read {path}')
            frames=[]
            for index in range(0,int(total),max(1,round(fps/8))):
                cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,bgr=cap.read()
                if not ok:continue
                h,w=bgr.shape[:2];scale=min(1,640/max(h,w));bgr=cv2.resize(bgr,(round(w*scale),round(h*scale)))
                image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
                f,ms=pose.predict(image,index/fps)
                frames.append({'time':index/fps,'features':asdict(f) if f else None,'pose_ms':ms,'index':index})
            cap.release();cache.write_text(json.dumps(frames))
        image_cache=cache.with_suffix('.images.json')
        images=json.loads(image_cache.read_text()) if image_cache.exists() else {}
        policy=hashlib.sha256((ROOT/'classifier.py').read_bytes()+b'crop-square-1.25-all22-threshold065-margin015-v1').hexdigest()
        if images.get('_policy_sha256')!=policy:images={}
        images['_policy_sha256']=policy
        two_hz=[];next_t=0
        for frame in frames:
            if frame['time']+1e-5>=next_t:two_hz.append(frame);next_t=frame['time']+.48
        if image_model:
            cap=cv2.VideoCapture(str(path))
            for frame in two_hz:
                k=str(frame['index'])
                if k in images and 'crop_exercise' in images[k]:continue
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame['index']);ok,bgr=cap.read()
                if not ok:raise RuntimeError(f'Cannot decode {path}')
                h,w=bgr.shape[:2];scale=min(1,640/max(h,w));bgr=cv2.resize(bgr,(round(w*scale),round(h*scale)))
                rgb=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
                pred=images.get(k) or image_model.predict(rgb, threshold=.65, margin=.15)
                if pred['exercise']=='unknown':
                    pose.predict(rgb,frame['time']);crop=pose.crop(rgb)
                    cropped=image_model.predict(crop, threshold=.65, margin=.15) if crop is not None else {}
                else:cropped={}
                images[k]={x:y for x,y in pred.items() if x!='scores'}
                images[k]['crop_exercise']=cropped.get('exercise','unknown')
            cap.release();image_cache.write_text(json.dumps(images))
        for hz,sequence in [(2,two_hz),(8,frames)]:
            rec=MovementRecognizer();pose_labels=[];hybrid=[];hybrid_motion=[];image_labels=[];events=[]
            for frame in sequence:
                f=Features(**frame['features']) if frame['features'] else None
                result=rec.update(f);pose_labels.append(result['exercise']);all_times.append(frame['pose_ms'])
                if result['exercise']!='unknown':events.append(frame['time'])
                image=images.get(str(frame['index']),{}).get('exercise','unknown')
                image_labels.append(image)
                hybrid_motion.append(image if image!='unknown' else result['exercise'])
                crop_label=images.get(str(frame['index']),{}).get('crop_exercise','unknown')
                hybrid.append(image if image!='unknown' else crop_label if crop_label!='unknown' else result['exercise'])
            for method,labels in [('pose',pose_labels)]+([('image',image_labels),('hybrid_motion',hybrid_motion),('hybrid',hybrid)] if image_model and hz==2 else []):
                stable=stable_labels(labels);known=[x for x in stable if x!='unknown'];truth=clip['expected']
                false=set(known)-{truth}
                rows.append({'clip':clip['path'],'expected':truth,'method':method,'hz':hz,'n':len(labels),
                    'correct':truth in known if truth!='unknown' else not known,'false_positive':bool(false),
                    'wrong_labels':sorted(false),'labelled_fraction':len(known)/max(1,len(labels)),
                    'first_correct_seconds':next((sequence[i]['time'] for i,x in enumerate(stable) if x==truth and truth!='unknown'),None)})
        print(clip['path'],[(r['method'],r['hz'],r['correct'],r['wrong_labels']) for r in rows if r['clip']==clip['path']],flush=True)
    pose.close()
    summary={}
    for hz in [2,8]:
        for method in ['pose','image','hybrid_motion','hybrid']:
            selected=[r for r in rows if r['hz']==hz and r['method']==method]
            if not selected:continue
            summary[f'{method}_{hz}hz']={'n':len(selected),'correct_clips':sum(r['correct'] for r in selected),
              'clips_with_wrong_accepted_label':sum(r['false_positive'] for r in selected),
              'per_class':{c:{'n':sum(r['expected']==c for r in selected),'correct':sum(r['correct'] for r in selected if r['expected']==c)} for c in sorted(set(r['expected'] for r in selected))}}
    output={'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['classifier.py','movement.py','hybrid.py','evaluate_movement.py']},'split':args.split,'selection':manifest['selection'],'metrics':'Target clip success: at least 3 consecutive correct outputs; negative success: no 3 consecutive target outputs. Also report any wrong accepted label. Includes startup, no frame accuracy claim.',
      'limitations':['No lateral-raise clips in this dataset selection.','No phone footage, no subject-disjoint guarantee; folder selections may share sources.','Development numbers are tuning results.','2 Hz ideal sampling omits network variability.','Pose/rule scores are not calibrated probabilities.'],
      'pose_latency_ms':{'median':float(np.median(all_times)),'p95':float(np.percentile(all_times,95))},'summary':summary,'rows':rows}
    dest=ROOT/f'results/movement_{args.split}.json';dest.write_text(json.dumps(output,indent=2));print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
