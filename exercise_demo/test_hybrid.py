"""Check session isolation and fallback policy without loading ML weights."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

class FakeImage:
    device='cpu'
    def predict(self,image,**kwargs):return dict(exercise=image,score=.8)
class FakePose:
    def predict(self,image,timestamp):return types.SimpleNamespace(value=image),1
    def crop(self,image):return None
    def close(self):pass
class FakeMovement:
    def __init__(self):self.count=0
    def update(self,feature):
        self.count+=1
        return {'exercise':'squat' if self.count>=3 else 'unknown'}

class HybridTests(unittest.TestCase):
    def model(self):
        spec=importlib.util.spec_from_file_location('hybrid_under_test',Path(__file__).with_name('hybrid.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fake=types.ModuleType('classifier');fake.ExerciseClassifier=FakeImage
        with patch.dict('sys.modules',{'classifier':fake}),patch.object(module,'PoseEstimator',FakePose),patch.object(module,'MovementRecognizer',FakeMovement):
            model=module.HybridClassifier()
            # Keep fake recognizer constructor for lazily-created sessions.
        module.MovementRecognizer=FakeMovement
        return model
    def test_clients_do_not_share_motion(self):
        m=self.model()
        for session in ['a','b','a','b']:self.assertEqual(m.predict('unknown',session)['exercise'],'unknown')
        self.assertEqual(m.predict('unknown','a')['exercise'],'squat')
    def test_stateless_client_does_not_get_temporal_label(self):
        m=self.model()
        for _ in range(10):self.assertEqual(m.predict('unknown')['exercise'],'unknown')
    def test_existing_accepted_label_has_priority(self):
        m=self.model()
        for _ in range(3):r=m.predict('pushup','a')
        self.assertEqual(r['exercise'],'pushup')
        self.assertEqual(r['source'],'image')
    def test_session_count_is_bounded(self):
        m=self.model()
        for i in range(50):m.predict('unknown',str(i))
        self.assertLessEqual(len(m.sessions),16)
if __name__=='__main__':unittest.main()
