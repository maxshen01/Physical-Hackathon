"""Pose ML + conservative temporal exercise evidence (scores are not probabilities).

Coordinates are converted to pixel aspect ratio before any geometric operation.
Only visible in-frame joints contribute; a completed cycle is needed for a label.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
from time import perf_counter
import math
import os
import numpy as np

from .paths import CACHE_ROOT
MODEL_PATH = CACHE_ROOT / 'pose/pose_landmarker_full.task'


def angle(a, b, c):
    u, v = np.asarray(a)-b, np.asarray(c)-b
    length = np.linalg.norm(u)*np.linalg.norm(v)
    return float(np.degrees(np.arccos(np.clip(np.dot(u,v)/length,-1,1)))) if length > 1e-6 else None


@dataclass
class Features:
    time: float
    upright: bool
    horizontal: bool
    knee: float | None
    elbow: float | None
    arm: float | None
    hip: float
    ankle_x: float | None
    ankle_y: float | None
    scale: float
    bilateral: bool
    arms_out: bool
    reason: str = 'tracking'


def extract_features(landmarks, width, height, timestamp):
    def point(i):
        p = landmarks[i]
        if min(p.visibility,p.presence) < .6 or not (0 <= p.x <= 1 and 0 <= p.y <= 1):
            return None
        return np.array([p.x*width/height,p.y])
    def mid(a,b):
        return (a+b)/2 if a is not None and b is not None else a if a is not None else b
    def joint(a,b,c):
        return angle(a,b,c) if all(x is not None for x in (a,b,c)) else None
    def mean(values):
        values = [x for x in values if x is not None]
        return float(np.mean(values)) if values else None
    ls,rs,lh,rh = [point(i) for i in (11,12,23,24)]
    shoulder,hip = mid(ls,rs),mid(lh,rh)
    if shoulder is None or hip is None:return None
    torso = float(np.linalg.norm(shoulder-hip))
    if torso < .07:return None
    le,re,lw,rw,lk,rk,la,ra = [point(i) for i in (13,14,15,16,25,26,27,28)]
    knees = [joint(lh,lk,la),joint(rh,rk,ra)]
    ankle = mid(la,ra)
    dx,dy = abs(shoulder[0]-hip[0]),hip[1]-shoulder[1]
    elbows = [joint(ls,le,lw),joint(rs,re,rw)]
    arms = [joint(lh,ls,le),joint(rh,rs,re)]
    # Both arms must abduct in opposite image directions, with extended elbows.
    arms_out = all(x is not None for x in (ls,rs,lw,rw))
    arms_out = bool(arms_out and all(e is not None and e > 145 for e in elbows)
        and (lw[0]-ls[0])*(rw[0]-rs[0]) < 0
        and abs(lw[0]-rw[0]) > 1.6*max(abs(ls[0]-rs[0]),torso*.35))
    return Features(timestamp,bool(dy > dx*.55 and dy > torso*.35), bool(dx > abs(dy)*1.2),
        mean(knees),mean(elbows),mean(arms),float(hip[1]),
        float(ankle[0]) if ankle is not None else None,
        float(ankle[1]) if ankle is not None else None,torso,
        bool(all(x is not None for x in knees) and abs(knees[0]-knees[1]) < 35),arms_out)


class PoseEstimator:
    """Stateless image inference: clients cannot contaminate each other's tracker."""
    def __init__(self, model_path=None):
        import mediapipe as mp
        self.mp = mp
        path = model_path or os.getenv('EXERCISE_POSE_PATH',str(MODEL_PATH))
        self.model = mp.tasks.vision.PoseLandmarker.create_from_options(mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=path, delegate=mp.tasks.BaseOptions.Delegate.CPU), num_poses=2,
            min_pose_detection_confidence=.6,min_pose_presence_confidence=.6))
    def predict(self,image,timestamp):
        start=perf_counter()
        rgb=np.ascontiguousarray(np.asarray(image.convert('RGB')))
        result=self.model.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=rgb))
        self.bounds=None
        if len(result.pose_landmarks)==1:
            visible=[p for p in result.pose_landmarks[0] if min(p.visibility,p.presence)>=.4 and 0<=p.x<=1 and 0<=p.y<=1]
            if len(visible)>=12:
                xs=[p.x*image.width for p in visible];ys=[p.y*image.height for p in visible]
                self.bounds=(min(xs),min(ys),max(xs),max(ys))
        features=extract_features(result.pose_landmarks[0],image.width,image.height,timestamp) if len(result.pose_landmarks)==1 else None
        return features, (perf_counter()-start)*1000
    def crop(self,image):
        if self.bounds is None:return None
        from PIL import Image
        x0,y0,x1,y1=self.bounds
        side=max(x1-x0,y1-y0)*1.25
        if side<40:return None
        cx,cy=(x0+x1)/2,(y0+y1)/2
        box=(round(cx-side/2),round(cy-side/2),round(cx+side/2),round(cy+side/2))
        # PIL pads an out-of-frame crop with black; full square preserves geometry.
        return image.crop(box)
    def close(self):self.model.close()


class Cycle:
    """Ordered rest → excursion → return, with hysteresis and time bounds."""
    def __init__(self, rest, peak, increasing=False):
        self.rest,self.peak,self.increasing=rest,peak,increasing
        self.reset()
    def reset(self):
        self.phase='seeking_start';self.started=None;self.rest_since=None;self.peak_time=None
    def update(self,t,value):
        if value is None:self.reset();return False
        resting = value <= self.rest if self.increasing else value >= self.rest
        peak = value >= self.peak if self.increasing else value <= self.peak
        if self.started is not None and t-self.started > 10:self.reset()
        if self.phase=='seeking_start':
            if resting:
                if self.rest_since is None:self.rest_since=t
                self.phase='ready'
            else:self.rest_since=None
        elif self.phase=='ready':
            if not resting:self.phase='moving';self.started=t
        if self.phase=='moving' and peak:self.phase='returning';self.peak_time=t
        elif self.phase=='returning' and resting:
            duration=t-self.started
            complete=.35 <= duration <= 10 and t-self.peak_time >= .12
            self.reset();self.phase='ready'
            return complete
        return False


class MovementRecognizer:
    def __init__(self):self.reset()
    def reset(self):
        self.cycles={'squat':Cycle(158,125),'pushup':Cycle(155,115),'lateral_raise':Cycle(30,65,True)}
        self.previous=None;self.smoothed={};self.anchor=None
        self.hip_starts={};self.hip_drops={}
        self.label='unknown';self.confirmed_at=-math.inf;self.last_evidence_at=-math.inf;self.reps=0;self.reason='waiting_for_movement'
    def update(self,f):
        if f is None:
            # Never display a stale label without visible pose. Preserve an incomplete
            # cycle across a single missed sample; the next timestamp enforces expiry.
            return dict(self.result(), exercise='unknown', reason='pose_missing_or_multiple_people')
        if self.previous is not None and (f.time <= self.previous.time or f.time-self.previous.time > 1.6):
            self.reset()
        dt=f.time-self.previous.time if self.previous else .5
        # Sudden camera/person translation or scale change invalidates the cycle.
        if self.previous and (abs(f.scale/self.previous.scale-1) > .75 or
            (f.ankle_x is not None and self.previous.ankle_x is not None and
             math.hypot(f.ankle_x-self.previous.ankle_x,f.ankle_y-self.previous.ankle_y) > f.scale*.65)):
            self.reset();self.reason='camera_or_person_moved'
        self.previous=f
        alpha=1-math.exp(-max(dt,0)/.14)
        previous_values=dict(self.smoothed)
        for name,value in [('knee',f.knee),('elbow',f.elbow),('arm',f.arm)]:
            if value is not None:self.smoothed[name]=self.smoothed.get(name,value)*(1-alpha)+value*alpha
            else:self.smoothed.pop(name,None)
        # Re-anchor feet in the standing rest phase: an early partial pose or
        # ordinary ankle-estimation drift must not poison later repetitions.
        if f.ankle_x is not None and (self.anchor is None or
            (f.upright and (f.knee or 0)>=158 and self.cycles['squat'].phase in ('seeking_start','ready'))):
            self.anchor=(f.ankle_x,f.ankle_y,f.hip,f.scale)
        stationary=self.anchor is not None and f.ankle_x is not None and math.hypot(f.ankle_x-self.anchor[0],f.ankle_y-self.anchor[1]) < f.scale*.65
        if not stationary:
            self.anchor=(f.ankle_x,f.ankle_y,f.hip,f.scale) if f.ankle_x is not None else None
        eligible={'squat':f.upright and stationary and f.knee is not None,
                  'pushup':f.horizontal and f.elbow is not None and (f.knee or 0)>145,
                  'lateral_raise':f.upright and stationary and f.bilateral and (f.knee or 0)>155}
        values={'squat':self.smoothed.get('knee'),'pushup':self.smoothed.get('elbow'),'lateral_raise':self.smoothed.get('arm')}
        for name,cycle in self.cycles.items():
            if not eligible[name]:
                cycle.reset();self.hip_starts.pop(name,None);self.hip_drops.pop(name,None);continue
            # Lateral raises require bilateral abduction at the top; rejects presses/curls.
            if name=='lateral_raise' and (values[name] or 0)>=65 and not f.arms_out:
                cycle.reset();continue
            if name=='squat':
                if cycle.phase in ('seeking_start','ready'):
                    self.hip_starts[name]=(f.hip,f.scale);self.hip_drops[name]=0.0
                if name in self.hip_starts:
                    base,scale=self.hip_starts[name]
                    self.hip_drops[name]=max(self.hip_drops[name],(f.hip-base)/scale)
            completed=cycle.update(f.time,values[name])
            if completed and (name!='squat' or self.hip_drops.get(name,0) >= .08):
                self.label=name;self.confirmed_at=f.time;self.last_evidence_at=f.time;self.reps+=1
        if self.label!='unknown':
            key={'squat':'knee','pushup':'elbow','lateral_raise':'arm'}[self.label]
            current=values[self.label];previous=previous_values.get(key)
            changing=current is not None and previous is not None and abs(current-previous)>=6
            continuing=eligible[self.label] and self.cycles[self.label].phase in ('moving','returning')
            if continuing and changing and f.time-self.confirmed_at<=10:
                self.last_evidence_at=f.time
            if not eligible[self.label] or f.time-self.last_evidence_at>2.2:self.label='unknown'
        self.reason='completed_cycle' if self.label!='unknown' else 'waiting_for_complete_cycle'
        return self.result()
    def result(self):
        return {'exercise':self.label,'reason':self.reason,'reps':self.reps,
                'phases':{k:v.phase for k,v in self.cycles.items()}}
