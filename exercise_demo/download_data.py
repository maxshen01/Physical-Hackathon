"""Download smoke-test assets; no credentials required."""
from pathlib import Path
import requests
from huggingface_hub import snapshot_download
ROOT=Path(__file__).resolve().parent
ASSETS={
 'workout-test.parquet':'https://huggingface.co/datasets/averrous/workout/resolve/main/data/test-00000-of-00001.parquet',
 'ucf101_subset.tar.gz':'https://huggingface.co/datasets/ambarishnarayan/UFC101_Subset_Workout/resolve/main/UCF101_subset.tar.gz',
 'DATASET_CARD.md':'https://huggingface.co/datasets/averrous/workout/raw/main/README.md',
}
if __name__=='__main__':
    (ROOT/'data').mkdir(exist_ok=True)
    for name,url in ASSETS.items():
        path=ROOT/'data'/name
        if path.exists():continue
        with requests.get(url,stream=True,timeout=120) as r:
            r.raise_for_status()
            temporary=path.with_suffix(path.suffix+'.partial')
            with temporary.open('wb') as f:
                for chunk in r.iter_content(1024*1024):f.write(chunk)
            temporary.replace(path)
    snapshot_download('prithivMLmods/Gym-Workout-Classifier-SigLIP2',local_dir=ROOT.parent/'.cache/model',allow_patterns=['config.json','preprocessor_config.json','model.safetensors'])
