"""Deterministic online-dataset smoke test; no training or parameter tuning."""
import io
import json
import tarfile
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from PIL import Image
from classifier import ExerciseClassifier, TARGETS

ROOT = Path(__file__).resolve().parent

def evaluate(per_class=20):
    model = ExerciseClassifier()
    table = pq.read_table(ROOT/'data/workout-test.parquet')
    metadata = json.loads(table.schema.metadata[b'huggingface'])
    names = metadata['info']['features']['label']['names']
    rows = table.to_pylist()
    rng = np.random.default_rng(42)
    selected = []
    # Target exercises plus confusable non-target classes for rejection checks.
    for label in ['squat', 'push up', 'lateral raises', 'plank', 'shoulder press']:
        candidates = [i for i, r in enumerate(rows) if names[r['label']] == label]
        selected.extend(rng.choice(candidates, min(per_class, len(candidates)), replace=False).tolist())
    results = []
    examples = []
    for i in selected:
        row = rows[i]
        image = Image.open(io.BytesIO(row['image']['bytes'])).convert('RGB')
        truth = names[row['label']]
        pred = model.predict(image)
        results.append(dict(source='workout_test', sample=str(i), truth=truth,
                            expected=TARGETS.get(truth,'unknown'), **{k:v for k,v in pred.items() if k!='scores'}))
        if sum(x[0] == truth for x in examples) < 3:
            examples.append((truth, pred, image.copy()))
        print(f'{len(results):3d}/{len(selected)} {truth:15s} → {pred["exercise"]:15s} ({pred["raw_label"]}, {pred["score"]:.2f})', flush=True)
    image_df = pd.DataFrame(results)
    image_df.to_csv(ROOT/'results/image_predictions.csv', index=False)
    confusion = pd.crosstab(image_df.expected, image_df.exercise)
    confusion.to_csv(ROOT/'results/image_confusion.csv')
    summary = {'model': model.model.config._name_or_path, 'device': model.device,
      'dataset': 'averrous/workout', 'split': 'test', 'seed':42,
      'threshold':0.65, 'margin':0.15, 'samples':len(results),
      'raw_top1_accuracy':float((image_df.truth == image_df.raw_label).mean()),
      'target_or_unknown_accuracy':float((image_df.expected == image_df.exercise).mean()),
      'median_inference_ms':float(image_df.inference_ms.median()),
      'per_class': {k: {'n':len(g), 'raw_correct':int((g.truth==g.raw_label).sum()),
                        'accepted_correct':int((g.expected==g.exercise).sum())} for k,g in image_df.groupby('truth')},
      'limitations':['Small sampled smoke test, not a benchmark.',
        'Model training data not disclosed; overlap with this image dataset cannot be excluded.',
        'No phone footage, simulator imagery, idle/walking or clinical validation in this image test.',
        'Threshold rejection is heuristic and not calibrated open-set recognition.']}
    # Read selected archive members explicitly, never extract archive paths.
    archive = ROOT/'data/ucf101_subset.tar.gz'
    video_rows=[]
    if archive.exists():
        out=ROOT/'data/ucf_samples'; out.mkdir(exist_ok=True)
        with tarfile.open(archive) as tar:
            for category, expected in [('PushUps','pushup'),('JumpingJack','unknown')]:
                members=sorted([m for m in tar.getmembers() if m.isfile() and f'/val/{category}/' in m.name and m.name.endswith('.avi')], key=lambda m:m.name)[:5]
                if not members: raise RuntimeError(f'No validation clips found for {category}')
                for member in members:
                    path=out/Path(member.name).name
                    path.write_bytes(tar.extractfile(member).read())
                    cap=cv2.VideoCapture(str(path)); total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); scores=[]
                    for frame in np.linspace(0,max(0,total-1),8,dtype=int):
                        cap.set(cv2.CAP_PROP_POS_FRAMES,int(frame)); ok,bgr=cap.read()
                        if ok:scores.append(model.predict(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
                    cap.release()
                    if not scores:raise RuntimeError(f'No frames decoded: {path}')
                    pred=Counter(x['exercise'] for x in scores).most_common(1)[0][0]
                    video_rows.append({'clip':path.name,'expected':expected,'prediction':pred,'frames':len(scores),'frame_labels':[x['exercise'] for x in scores]})
                    print('VIDEO',path.name,expected,pred,flush=True)
        pd.DataFrame(video_rows).to_csv(ROOT/'results/video_predictions.csv',index=False)
        summary['video_smoke_test']={'dataset':'ambarishnarayan/UFC101_Subset_Workout','split':'val','selection':'First five lexicographically sorted clips per class; 8 uniformly spaced frames; majority vote',
          'n':len(video_rows),'correct':sum(r['expected']==r['prediction'] for r in video_rows), 'rows':video_rows}
    (ROOT/'results/summary.json').write_text(json.dumps(summary,indent=2))
    # Contact sheet for visual inspection of inputs and outputs.
    from PIL import ImageDraw
    sheet=Image.new('RGB',(900,240*5),'white'); draw=ImageDraw.Draw(sheet)
    for n,(truth,pred,image) in enumerate(examples):
        x=(n%3)*300;y=(n//3)*240
        image.thumbnail((290,185));sheet.paste(image,(x,y))
        draw.text((x+4,y+188),f'True: {truth}',fill='black')
        draw.text((x+4,y+204),f'Pred: {pred["exercise"]} ({pred["score"]:.2f})',fill='black')
    sheet.save(ROOT/'results/examples.jpg')
    print(json.dumps(summary,indent=2))
    return image_df,summary

if __name__=='__main__':evaluate()
