"""Evaluate the original UCF smoke-test failures with the frozen hybrid pipeline."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest_path=ROOT/'data/motion/manifest.json';manifest=json.loads(manifest_path.read_text())
for path in sorted((ROOT/'data/ucf_samples').glob('*.avi')):
    relative='../ucf_samples/'+path.name
    if any(c['path']==relative for c in manifest['clips']):continue
    manifest['clips'].append({'path':relative,'split':'holdout','source_member':'ambarishnarayan/UFC101_Subset_Workout/val/'+path.name,'expected':'pushup' if 'PushUps' in path.name else 'unknown','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
manifest_path.write_text(json.dumps(manifest,indent=2))
