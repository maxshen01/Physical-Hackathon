"""Image-plane research features. No coaching or anatomical angle claims."""
import math
import numpy as np
from .movement import angle

METRICS = {
    'squat': {'knee_left_deg': (23,25,27), 'knee_right_deg': (24,26,28)},
    'pushup': {'elbow_left_deg': (11,13,15), 'elbow_right_deg': (12,14,16),
               'body_alignment_left_deg': (11,23,27), 'body_alignment_right_deg': (12,24,28)},
    'lateral_raise': {'arm_left_deg': (23,11,13), 'arm_right_deg': (24,12,14)},
}


def extract_pose_features(poses, width, height, timestamp, exercise):
    metrics = dict(METRICS[exercise])
    if exercise == 'squat': metrics['torso_inclination_deg'] = (11,12,23,24)
    if exercise == 'pushup':
        metrics.update(hip_offset_left_torso_lengths=(11,23,27), hip_offset_right_torso_lengths=(12,24,28))
    if exercise == 'lateral_raise': metrics['arm_difference_deg'] = (23,11,13,24,12,14)
    output = {}
    for name, ids in metrics.items():
        reason = None
        value = None
        quality = None
        if len(poses) != 1:
            reason = 'no_person' if not poses else 'multiple_people'
        else:
            joints = [poses[0][i] for i in ids]
            quality = min(min(p.visibility, p.presence) for p in joints)
            if quality < .6: reason = 'low_landmark_confidence'
            elif any(not (0 <= p.x <= 1 and 0 <= p.y <= 1) for p in joints): reason = 'joint_out_of_frame'
            else:
                points = [np.array([p.x*width, p.y*height]) for p in joints]
                if name == 'torso_inclination_deg':
                    shoulder = (points[0]+points[1])/2
                    hip = (points[2]+points[3])/2
                    value = angle(shoulder, hip, hip+np.array([0,-1]))
                elif name == 'arm_difference_deg':
                    left, right = angle(*points[:3]), angle(*points[3:])
                    value = abs(left-right) if left is not None and right is not None else None
                elif name.startswith('hip_offset'):
                    shoulder, hip, ankle = points
                    axis = ankle-shoulder
                    torso = np.linalg.norm(hip-shoulder)
                    length = np.linalg.norm(axis)
                    # Signed displacement along image-up normal; positive = hip above body line.
                    if length > 1e-6 and torso > 1e-6:
                        normal = np.array([axis[1], -axis[0]])/length
                        if normal[1] > 0: normal = -normal
                        value = float(np.dot(hip-shoulder, normal)/torso)
                else: value = angle(*points)
                if value is None or not math.isfinite(value): value = None; reason = 'degenerate_geometry'
        output[name] = {'value': round(value,3) if value is not None else None,
                        'landmark_quality': float(quality) if quality is not None else None,
                        'unavailable_reason': reason}
    return {'timestamp_ms': timestamp, 'features': output}


def summarize(exercise, frames):
    ranges = {}
    for key in (frames[0]['features'] if frames else []):
        readings = [(f['features'][key]['value'], f['timestamp_ms']) for f in frames
                    if f['features'][key]['value'] is not None]
        low = min(readings, key=lambda r: r[0]) if readings else (None, None)
        high = max(readings, key=lambda r: r[0]) if readings else (None, None)
        ranges[key] = {'min': low[0], 'max': high[0], 'min_timestamp_ms': low[1],
                       'max_timestamp_ms': high[1], 'valid_frames': len(readings), 'total_frames': len(frames)}
    valid = [i for i,f in enumerate(frames) if any(v['value'] is not None for v in f['features'].values())]
    review = []
    if valid:
        keys = {'squat': ('knee_left_deg','knee_right_deg'), 'pushup': ('elbow_left_deg','elbow_right_deg'),
                'lateral_raise': ('arm_left_deg','arm_right_deg')}[exercise]
        scored = [(i, np.mean([frames[i]['features'][k]['value'] for k in keys if frames[i]['features'][k]['value'] is not None]))
                  for i in valid if any(frames[i]['features'][k]['value'] is not None for k in keys)]
        peak = (max if exercise == 'lateral_raise' else min)(scored, key=lambda x:x[1])[0] if scored else valid[len(valid)//2]
        review = sorted(set([valid[0],peak,valid[-1]]))
    return {'exercise': exercise, 'status': 'features_available' if valid else 'unable_to_extract',
            'measurement_space': '2d_image_plane', 'ranges': ranges, 'frames': frames, 'review_frame_indices': review,
            'complete_repetition_verified': False}
