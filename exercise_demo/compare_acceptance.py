import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from classifier import ExerciseClassifier,TARGETS
from PIL import Image
ROOT=Path(__file__).resolve().parent

def select(scores,policy):
    ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)
    label,score=ranked[0]
    if policy in ('current','relaxed'):
        threshold,margin=(.65,.15) if policy=='current' else (.25,.03)
        return TARGETS[label] if label in TARGETS and score>=threshold and score-ranked[1][1]>=margin else 'unknown'
    targets=sorted([(k,scores[k]) for k in TARGETS],key=lambda x:x[1],reverse=True)
    top,p=targets[0];mass=sum(v for _,v in targets)
    if policy=='three_only':return TARGETS[top]
    return TARGETS[top] if p>=.10 and mass>0 and p/mass>=.60 and (p-targets[1][1])/mass>=.15 else 'unknown'

if __name__=='__main__':
    cache=ROOT/'results/acceptance_scores.json'
    if cache.exists():records=json.loads(cache.read_text())
    else:
        model=ExerciseClassifier();records=[]
        for clip in json.loads((ROOT/'data/real_web_tests/replay.json').read_text()):
            samples=[]
            for path in clip['frames']:
                r=model.predict(Image.open(path));samples.append(r['scores'])
            records.append(dict(name=clip['name'],id=clip['subject'],expected=clip['expected'],scores=samples))
            print(clip['name'],clip['subject'],flush=True)
        cache.write_text(json.dumps(records))
    report={}
    for policy in ['current','relaxed','guarded_three','three_only']:
        rows=[]
        for c in records:
            raw=[select(s,policy) for s in c['scores']];display=[];history=[]
            for value in raw:
                history=(history+[value])[-3:]
                display.append(value if len(history)==3 and len(set(history))==1 else 'unknown')
            majority=Counter(display).most_common(1)[0][0]
            rows.append(dict(name=c['name'],id=c['id'],expected=c['expected'],majority=majority,any_correct=c['expected'] in display,wrong_frames=sum(x not in ('unknown',c['expected']) for x in display),raw=raw,display=display))
        summary={}
        for expected in ['squat','pushup','lateral_raise','unknown']:
            group=[r for r in rows if r['expected']==expected]
            summary[expected]={'n':len(group),'majority_correct':sum(r['majority']==expected for r in group),'any_correct':sum(r['any_correct'] for r in group),'wrong_frames':sum(r['wrong_frames'] for r in group)}
        report[policy]={'summary':summary,'clips':rows}
    (ROOT/'results/acceptance_comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v['summary'] for k,v in report.items()},indent=2))
