import json
from pathlib import Path
import cv2
from download_web_tests import SELECTION
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/web_tests'
if __name__=='__main__':
    records=json.loads((DATA/'exercises.json').read_text());replays=[]
    for name,expected in SELECTION.items():
        record=next(r for r in records if r['name']==name)
        for subject,url in record['videos'].items():
            path=DATA/f'{expected}_{record["id"]}_{subject}.mp4'
            if not path.exists():continue
            cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if not cap.isOpened() or fps<=0:raise RuntimeError(f'Cannot decode {path}')
            out=DATA/'frames'/path.stem;out.mkdir(parents=True,exist_ok=True)
            frames=[]
            # First 12 seconds at 2Hz, matching app's maximum request rate.
            for n in range(min(24,int(count/fps*2))):
                cap.set(cv2.CAP_PROP_POS_MSEC,n*500);ok,bgr=cap.read()
                if not ok:break
                h,w=bgr.shape[:2];scale=min(1,640/max(h,w));bgr=cv2.resize(bgr,(round(w*scale),round(h*scale)))
                target=out/f'{n:03d}.jpg';cv2.imwrite(str(target),bgr,[cv2.IMWRITE_JPEG_QUALITY,85]);frames.append(str(target.resolve()))
            cap.release()
            replays.append({'name':name,'expected':expected,'subject':subject,'url':url,'frames':frames})
    (DATA/'replay.json').write_text(json.dumps(replays,indent=2))
    print(len(replays),'clips;',sum(len(x['frames']) for x in replays),'frames')
