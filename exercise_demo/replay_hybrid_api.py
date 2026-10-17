"""Real-cadence HTTPS replay; exercises session isolation and native display rule."""
import argparse,io,json,time
from pathlib import Path
import cv2,numpy as np,requests
from PIL import Image
from evaluate_movement import stable_labels
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--endpoint',default='https://127.0.0.1:8444');args=parser.parse_args()
manifest=json.loads((ROOT/'data/motion/manifest.json').read_text())
clip=next(c for c in manifest['clips'] if c['path'].startswith('holdout/squat/1e2'))
cap=cv2.VideoCapture(str(ROOT/'data/motion'/clip['path']));fps=cap.get(cv2.CAP_PROP_FPS);total=cap.get(cv2.CAP_PROP_FRAME_COUNT)
labels=[];rows=[];session=requests.Session();begin=time.monotonic()
for i,index in enumerate(range(0,int(min(total,fps*12)),round(fps/2))):
    time.sleep(max(0,begin+i*.5-time.monotonic()))
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,bgr=cap.read()
    if not ok:raise RuntimeError('Video decode failed')
    h,w=bgr.shape[:2];scale=min(1,640/max(h,w));bgr=cv2.resize(bgr,(round(w*scale),round(h*scale)))
    data=io.BytesIO();Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).save(data,format='JPEG',quality=85)
    start=time.monotonic()
    r=session.post(args.endpoint+'/predict',headers={'X-Movement-Session':'real-cadence-'+str(int(begin))},files={'file':('frame.jpg',data.getvalue(),'image/jpeg')},verify=str(ROOT.parent/'.cache/tls/demo-ca.pem'),timeout=10)
    r.raise_for_status();label=r.json()['exercise'];labels.append(label)
    rows.append({'time':index/fps,'exercise':label,'elapsed_ms':(time.monotonic()-start)*1000})
cap.release()
stable=stable_labels(labels)
report={'clip':clip['path'],'endpoint':args.endpoint,'expected':clip['expected'],'correct_display_seen':clip['expected'] in stable,'median_round_trip_ms':float(np.median([r['elapsed_ms'] for r in rows][1:])),'p95_round_trip_ms':float(np.percentile([r['elapsed_ms'] for r in rows][1:],95)),'rows':rows,'display':stable}
(ROOT/'results/movement_api_replay.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
assert report['correct_display_seen'],'The real-cadence HTTPS replay did not recognise this squat'
