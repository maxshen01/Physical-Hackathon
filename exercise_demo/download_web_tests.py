"""Small, fixed set of web demonstration videos; sources recorded, not redistributed."""
import json, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/web_tests'
SELECTION={'Squat':'squat','Push-Up':'pushup','Dumbbell Lateral Raise':'lateral_raise','Dumbbell Front Raise':'unknown','Front Plank':'unknown'}

def download(item):
    path=DATA/item['file']
    if not path.exists():
        r=requests.get(item['url'],timeout=120);r.raise_for_status();path.write_bytes(r.content)
    item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return item

if __name__=='__main__':
    DATA.mkdir(parents=True,exist_ok=True)
    meta=DATA/'exercises.json'
    if not meta.exists():
        r=requests.get('https://raw.githubusercontent.com/luisaraujoc/free-exercise-db-api/main/data/exercises.json',timeout=30);r.raise_for_status();meta.write_bytes(r.content)
    records=json.loads(meta.read_text());items=[]
    for name,label in SELECTION.items():
        record=next(r for r in records if r['name']==name)
        for subject,url in record['videos'].items():
            items.append({'name':name,'expected':label,'subject':subject,'url':url,'file':f'{label}_{record["id"]}_{subject}.mp4','source':'https://github.com/luisaraujoc/free-exercise-db-api'})
    with ThreadPoolExecutor(max_workers=3) as pool:items=list(pool.map(download,items))
    (DATA/'manifest.json').write_text(json.dumps(items,indent=2))
    print('Downloaded',len(items),'clips')
