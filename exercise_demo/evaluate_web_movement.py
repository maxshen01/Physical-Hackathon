"""Replay separately sourced web demos at the native client's 2 Hz cadence."""
import json
from pathlib import Path
from PIL import Image
from classifier import ExerciseClassifier
from movement import MovementRecognizer,PoseEstimator
from evaluate_movement import stable_labels

ROOT=Path(__file__).resolve().parent
pose=PoseEstimator();image=ExerciseClassifier();rows=[]
for clip in json.loads((ROOT/'data/web_tests/replay.json').read_text()):
    rec=MovementRecognizer();labels={k:[] for k in ['image','pose','hybrid']};ms=[]
    for i,path in enumerate(clip['frames']):
        frame=Image.open(path).convert('RGB');f,t=pose.predict(frame,i/2);ms.append(t)
        motion=rec.update(f)['exercise'];prediction=image.predict(frame)['exercise']
        labels['pose'].append(motion);labels['image'].append(prediction)
        crop=pose.crop(frame) if prediction=='unknown' else None
        cropped=image.predict(crop)['exercise'] if crop is not None else 'unknown'
        labels['hybrid'].append(prediction if prediction!='unknown' else cropped if cropped!='unknown' else motion)
    for method,values in labels.items():
        stable=stable_labels(values);known=[v for v in stable if v!='unknown'];truth=clip['expected']
        rows.append({'clip':clip['name']+' '+clip['subject'],'source':clip['url'],'expected':truth,'method':method,
            'frames':len(values),'correct':truth in known if truth!='unknown' else not known,
            'wrong_labels':sorted(set(known)-{truth}),'labelled_frames':len(known),'labels':stable})
    print(clip['name'],clip['subject'],[(r['method'],r['correct'],r['wrong_labels']) for r in rows[-3:]],flush=True)
pose.close()
(ROOT/'results/movement_web.json').write_text(json.dumps({'description':'2 Hz public demonstration clips, three-response display smoothing; not phone footage or participant-disjoint evaluation.','rows':rows},indent=2))
