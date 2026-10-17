"""Existing image classifier with session-isolated temporal pose fallback."""
from collections import OrderedDict
from time import monotonic, perf_counter
from .movement import MovementRecognizer, PoseEstimator

class HybridClassifier:
    def __init__(self):
        from .image import ExerciseClassifier
        self.image=ExerciseClassifier()
        self.pose=PoseEstimator()
        self.sessions=OrderedDict()
        self.device=f'{self.image.device}+pose-cpu'
    def predict(self,image,session_id=None):
        start=perf_counter();now=monotonic()
        result=self.image.predict(image, threshold=.65, margin=.15)
        result.update(source='image' if result['exercise']!='unknown' else 'unknown',
                      movement={'reason':'session_header_required','exercise':'unknown'},pose_ms=None)
        # Stateless clients retain the image API without mixing motion histories.
        if session_id:
            for key,(_,seen) in list(self.sessions.items()):
                if now-seen>12:del self.sessions[key]
            recognizer,_=self.sessions.pop(session_id,(MovementRecognizer(),now))
            feature,ms=self.pose.predict(image,now)
            motion=recognizer.update(feature)
            self.sessions[session_id]=(recognizer,now)
            while len(self.sessions)>16:self.sessions.popitem(last=False)
            result.update(movement=motion,pose_ms=ms,
                          pose_features=vars(feature) if feature else None)
            if result['exercise']=='unknown':
                crop=self.pose.crop(image)
                if crop is not None:
                    cropped=self.image.predict(crop, threshold=.65, margin=.15)
                    result['crop_label']=cropped.get('raw_label');result['crop_score']=cropped.get('score')
                    if cropped['exercise']!='unknown':
                        result.update(exercise=cropped['exercise'],source='person_crop')
            if result['exercise']=='unknown' and motion['exercise']!='unknown':
                result.update(exercise=motion['exercise'],source='movement')
        result['inference_ms']=(perf_counter()-start)*1000
        return result
    def close(self):self.pose.close()
