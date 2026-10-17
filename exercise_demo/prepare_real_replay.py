"""Create a native-client replay manifest from downloaded public clips."""
import json,hashlib
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/real_web_tests'
SOURCE='https://huggingface.co/datasets/RickyRiccio/Real_Time_Exercise_Recognition_Dataset'
if __name__=='__main__':
    original=json.loads((ROOT/'data/motion/manifest.json').read_text())['clips']
    selected=[]
    for category in ['squat','push-up','shoulder press','barbell biceps curl']:
        clips=sorted([x for x in original if x['split']=='holdout' and f'/{category}/' in x['path']],key=lambda x:x['path'])[:3]
        for c in clips:selected.append(dict(c,path=str(ROOT/'data/motion'/c['path']),name=category,url=SOURCE+'#'+c['source_member']))
    lateral=DATA/'lateral_manifest.json'
    if lateral.exists():
        for c in json.loads(lateral.read_text()):selected.append(dict(c,name='lateral raise',url='https://www.kaggle.com/datasets/hasyimabdillah/workoutfitness-video#'+c['source_member']))
    replay=[]
    for item in selected:
        path=Path(item['path']);cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or fps<=0:raise RuntimeError(str(path))
        out=DATA/'frames'/path.stem;out.mkdir(parents=True,exist_ok=True);frames=[]
        for n in range(min(24,int(count/fps*2))):
            cap.set(cv2.CAP_PROP_POS_MSEC,n*500);ok,bgr=cap.read()
            if not ok:break
            h,w=bgr.shape[:2];scale=min(1,640/max(h,w));bgr=cv2.resize(bgr,(round(w*scale),round(h*scale)))
            target=out/f'{n:03d}.jpg';cv2.imwrite(str(target),bgr,[cv2.IMWRITE_JPEG_QUALITY,85]);frames.append(str(target.resolve()))
        cap.release()
        replay.append({'name':item['name'],'expected':item['expected'],'subject':path.stem,'url':item['url'],'frames':frames})
    (DATA/'replay.json').write_text(json.dumps(replay,indent=2))
    (DATA/'sources.json').write_text(json.dumps(selected,indent=2))
    print(len(replay),'clips;',sum(len(x['frames']) for x in replay),'frames')
