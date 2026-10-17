"""Live model estimate for display; never changes acceptance or session locking."""
import math

NAMES={'squat':'Squat','pushup':'Push-up','push up':'Push-up','push-up':'Push-up',
       'lateral_raise':'Lateral raise','lateral raise':'Lateral raise','lateral raises':'Lateral raise'}
ALLOWED_EXERCISES={'squat','pushup','lateral_raise'}

def prediction_preview(result):
    if result.get('preview_discarded'):
        return {'preview_label':'Unknown','preview_score':None,'preview_source':'image'}
    source=result.get('source')
    if result.get('cloud_confirmed') and source=='openai_vision':
        label=result.get('display_name') or result['exercise'].replace('_',' ').capitalize()
        score=None
    elif source=='movement':
        label=NAMES.get(result['exercise'],result['exercise'].replace('_',' ').capitalize())
        score=None
    elif source=='person_crop':
        label=result.get('crop_label') or result.get('raw_label') or 'unknown'
        score=result.get('crop_score')
    else:
        source='image';label=result.get('raw_label') or result.get('exercise','unknown')
        score=result.get('score')
    label=NAMES.get(str(label).lower(),'Unknown')
    if label=='Unknown':score=None
    if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1:score=None
    return {'preview_label':label,'preview_score':score,'preview_source':source}
