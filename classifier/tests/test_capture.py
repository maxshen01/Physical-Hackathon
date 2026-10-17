import io
import json
import unittest
from types import SimpleNamespace as Point
from unittest.mock import Mock
from PIL import Image
from fastapi.testclient import TestClient
from kinevoa_classifier.capture import extract_pose_features, summarize
from kinevoa_classifier.api import create_app

class CaptureTests(unittest.TestCase):
    def test_geometry_and_missing_quality(self):
        points=[Point(x=.5,y=.5,visibility=1.,presence=1.) for _ in range(33)]
        points[23].x=.3;points[23].y=.2
        points[25].x=.3;points[25].y=.5
        points[27].x=.6;points[27].y=.5
        result=extract_pose_features([points],640,480,100,'squat')['features']
        self.assertEqual(result['knee_left_deg']['value'],90)
        points[25].visibility=.2
        result=extract_pose_features([points],640,480,100,'squat')['features']
        self.assertIsNone(result['knee_left_deg']['value'])
        self.assertEqual(result['knee_left_deg']['unavailable_reason'],'low_landmark_confidence')

    def test_no_person_and_multiple_people(self):
        for poses,reason in [([], 'no_person'),([[],[]], 'multiple_people')]:
            frame=extract_pose_features(poses,640,480,0,'pushup')
            self.assertTrue(all(f['value'] is None and f['unavailable_reason']==reason for f in frame['features'].values()))
            self.assertEqual(summarize('pushup',[frame])['review_frame_indices'],[])

    def test_ranges_exclude_missing_and_keep_extreme_timestamps(self):
        frames = [extract_pose_features([],640,480,t,'squat') for t in (0,100,200,300)]
        for frame, value in zip(frames, (170, None, 90, 170)):
            frame['features']['knee_left_deg']['value'] = value
        result = summarize('squat',frames)
        self.assertEqual(result['ranges']['knee_left_deg'], {
            'min':90, 'max':170, 'min_timestamp_ms':200, 'max_timestamp_ms':0,
            'valid_frames':3, 'total_frames':4})
        missing = result['ranges']['knee_right_deg']
        self.assertIsNone(missing['min'])
        self.assertIsNone(missing['max_timestamp_ms'])
        self.assertEqual(missing['valid_frames'],0)

    def test_capture_api(self):
        model=Mock();model.pose.landmarks.return_value=[]
        cloud=Mock()
        app=create_app(classifier_factory=lambda:model,vision_factory=lambda:cloud)
        image=io.BytesIO();Image.new('RGB',(64,48)).save(image,format='JPEG')
        def files(payload=None):return [('files',('frame.jpg',image.getvalue() if payload is None else payload,'image/jpeg')) for _ in range(3)]
        with TestClient(app) as client:
            data={'exercise':'squat','timestamps':json.dumps([0,100,200])}
            response=client.post('/capture/features',data=data,files=files())
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['status'],'unable_to_extract')
            self.assertFalse(response.json()['complete_repetition_verified'])
            self.assertEqual(model.pose.landmarks.call_count,3)
            model.pose.landmarks.reset_mock()
            for payload in (b'',b'corrupt'):
                self.assertEqual(client.post('/capture/features',data=data,files=files(payload)).status_code,400)
            self.assertEqual(client.post('/capture/features',data={**data,'timestamps':'[0,0,1]'},files=files()).status_code,400)
            self.assertEqual(client.post('/capture/features',data={**data,'exercise':'unknown'},files=files()).status_code,400)
            model.pose.landmarks.assert_not_called()
            model.pose.landmarks.side_effect = RuntimeError('model failed')
            failed = client.post('/capture/features',data=data,files=files())
            self.assertEqual(failed.status_code,503)
            self.assertIn('Local pose extraction failed',failed.json()['detail'])
            cloud.update.assert_not_called()
            model.predict.assert_not_called()
