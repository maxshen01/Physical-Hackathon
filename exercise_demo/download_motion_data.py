import io,zipfile,requests
URL='https://huggingface.co/datasets/RickyRiccio/Real_Time_Exercise_Recognition_Dataset/resolve/main/Real-Time%20Exercise%20Recognition%20Dataset.zip'
class Remote(io.RawIOBase):
 def __init__(self):
  self.pos=0; self.size=3092287218
 def seekable(self): return True
 def tell(self): return self.pos
 def seek(self,offset,whence=0):
  self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
  return self.pos
 def read(self,n=-1):
  if n<0:n=self.size-self.pos
  if not n:return b''
  r=requests.get(URL,params={'range_start':str(self.pos)},headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'},timeout=60)
  r.raise_for_status()
  if r.status_code!=206:raise RuntimeError(f'Range not honoured: {r.status_code}')
  self.pos+=len(r.content);return r.content
if __name__=='__main__':
 import json,hashlib
 from pathlib import Path
 root=Path(__file__).resolve().parent/'data/motion'
 root.mkdir(parents=True,exist_ok=True)
 manifest=[]
 with zipfile.ZipFile(Remote()) as z:
  for split,prefix in [('development','final_kaggle_with_additional_video'),('holdout','similar_dataset')]:
   for category,label in [('squat','squat'),('push-up','pushup'),('shoulder press','unknown'),('barbell biceps curl','unknown')]:
    candidates=sorted(n for n in z.namelist() if n.startswith(f'{prefix}/{category}/') and n.endswith(('.mp4','.avi')))
    for name in candidates[:5]:
     path=root/split/category/name.split('/')[-1]
     path.parent.mkdir(parents=True,exist_ok=True)
     if not path.exists():path.write_bytes(z.read(name))
     manifest.append({'path':str(path.relative_to(root)), 'split':split,'source_member':name,'expected':label,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
     print(split,name,flush=True)
 existing=json.loads((root/'manifest.json').read_text()).get('clips',[]) if (root/'manifest.json').exists() else []
 by_path={r['path']:r for r in existing};by_path.update({r['path']:r for r in manifest});manifest=list(by_path.values())
 (root/'manifest.json').write_text(json.dumps({'dataset':'RickyRiccio/Real_Time_Exercise_Recognition_Dataset','selection':'First five lexicographic mp4/avi files per category and source folder; no subject-disjoint guarantee','clips':manifest},indent=2))
