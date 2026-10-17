"""Fixed selection of real lateral raises and confusable non-target exercises."""
import json,hashlib
from pathlib import Path
from urllib.parse import quote
import requests
ROOT=Path(__file__).resolve().parents[1]/'data/motion'
tree=requests.get('https://api.github.com/repos/krishwin/FitCenter-1/git/trees/main?recursive=1',timeout=30).json()
revision=tree['sha'];rows=[]
for category,expected in [('lateral raise','lateral_raise'),('deadlift','unknown'),('bench press','unknown'),('chest fly machine','unknown')]:
    names=sorted(x['path'] for x in tree['tree'] if x['path'].startswith(f'Data/videos/{category}/') and x['path'].endswith('.mp4'))
    for i,name in enumerate(names if expected=='lateral_raise' else names[:5]):
        split='development' if expected=='lateral_raise' and i<5 else 'final'
        relative=f'{split}/{category}/{name.split("/")[-1]}'
        path=ROOT/relative;path.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://raw.githubusercontent.com/krishwin/FitCenter-1/{revision}/{quote(name)}'
        if not path.exists():
            r=requests.get(url,timeout=60);r.raise_for_status();path.write_bytes(r.content)
        rows.append({'path':relative,'split':split,'source_member':url,'expected':expected,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(relative,flush=True)
(ROOT/'lateral_manifest.json').write_text(json.dumps(rows,indent=2))

manifest_path=ROOT/'manifest.json'
manifest=json.loads(manifest_path.read_text())
by_path={c['path']:c for c in manifest['clips']}
by_path.update({c['path']:c for c in rows})
manifest['clips']=list(by_path.values())
manifest_path.write_text(json.dumps(manifest,indent=2))
