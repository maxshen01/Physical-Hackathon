"""Opt-in short live check: records numeric diagnostics only, never camera frames."""
import argparse,json,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=45);parser.add_argument('--expected',choices=['squat','pushup','lateral_raise','unknown'],default='squat');args=parser.parse_args()
start=time.time();seen={};client=requests.Session()
while time.time()-start<args.seconds:
    r=client.get('https://127.0.0.1:8443/diagnostics',verify=str(ROOT.parent/'.cache/tls/demo-ca.pem'),timeout=5);r.raise_for_status()
    for item in r.json()['recent']:
        if item['time']>=start and str(item['time']) not in seen:
            seen[str(item['time'])]=item
            print(json.dumps({'time':round(item['time']-start,1),'exercise':item['exercise'],'source':item.get('source'),'movement':item.get('movement')}),flush=True)
    time.sleep(1)
rows=list(seen.values());report={'expected':args.expected,'duration_seconds':args.seconds,'samples':len(rows),'rows':rows,'limitation':'User-labelled live trial. Not independent ground truth or a benchmark; no video retained.'}
(ROOT/'results/movement_live.json').write_text(json.dumps(report,indent=2))
print('Captured',len(rows),'numeric predictions',flush=True)
