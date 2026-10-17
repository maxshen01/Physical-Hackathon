"""API boundary tests without loading or downloading model weights."""
import io
import unittest
from unittest.mock import patch
from PIL import Image



class FakeClassifier:
    device = 'test'

    def close(self): pass

    def predict(self, image, session_id=None):
        assert image.mode == 'RGB'
        return {'exercise': 'squat', 'score': 0.99, 'raw_label': 'squat'}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kinevoa_classifier.api import create_app
        cls.app = create_app(classifier_factory=FakeClassifier)

    def test_documented_schema_matches_server(self):
        import json
        from pathlib import Path
        contract = Path(__file__).resolve().parents[2] / 'contracts/classifier.openapi.json'
        self.assertEqual(self.app.openapi(), json.loads(contract.read_text()))

    def test_application_state_is_independent(self):
        from kinevoa_classifier.api import create_app
        from fastapi.testclient import TestClient
        other = create_app(classifier_factory=FakeClassifier)
        with TestClient(self.app), TestClient(other):
            self.assertIsNot(self.app.state.model, other.state.model)
            self.assertIsNot(self.app.state.vision, other.state.vision)

    def test_image_response_contains_only_exercise(self):
        from fastapi.testclient import TestClient
        data = io.BytesIO()
        Image.new('RGBA', (32, 48), 'white').save(data, format='PNG')
        with TestClient(self.app) as client:
            response = client.post('/predict', files={'file': ('frame.png', data.getvalue(), 'image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'exercise': 'squat'})

    def test_unmapped_cloud_response_is_discarded(self):
        from fastapi.testclient import TestClient
        data = io.BytesIO(); Image.new('RGB', (32,48),'white').save(data,format='JPEG')
        with TestClient(self.app) as client:
            with patch.object(self.app.state.vision,'update',return_value={'exercise':'lunge','display_name':'Lunge','source':'openai_vision','cloud_confirmed':True,'cloud_checks':2,'cloud_status':'confirmed'}):
                response=client.post('/predict',headers={'X-Movement-Session':'unit-session'},files={'file':('frame.jpg',data.getvalue(),'image/jpeg')})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['exercise'],'unknown')
        self.assertNotIn('display_name',response.json())
        self.assertNotIn('cloud_confirmed',response.json())
        self.assertEqual(response.json()['preview_label'],'Unknown')

    def test_live_preview_includes_rejected_leader(self):
        from fastapi.testclient import TestClient
        data=io.BytesIO();Image.new('RGB',(32,48),'white').save(data,format='JPEG')
        with TestClient(self.app) as client:
            with patch.object(self.app.state.model,'predict',return_value={'exercise':'unknown','raw_label':'shoulder press','score':.42}), patch.object(self.app.state.vision,'update',return_value={'cloud_status':'disabled'}):
                response=client.post('/predict',headers={'X-Movement-Session':'preview-test'},files={'file':('frame.jpg',data.getvalue(),'image/jpeg')})
        self.assertEqual(response.json()['exercise'],'unknown')
        self.assertEqual(response.json()['preview_label'],'Unknown')
        self.assertIsNone(response.json()['preview_score'])

    def test_invalid_image_is_rejected(self):
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post('/predict', files={'file': ('frame.jpg', b'not an image', 'image/jpeg')})
        self.assertEqual(response.status_code, 400)

    def test_oversized_upload_is_rejected(self):
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post('/predict', files={'file': ('frame.jpg', b'x' * (8 * 1024 * 1024 + 1), 'image/jpeg')})
        self.assertEqual(response.status_code, 413)

    def test_page_includes_mobile_camera(self):
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('getUserMedia', response.text)
        self.assertIn('playsinline', response.text)
        self.assertNotIn('JSON.stringify', response.text)


if __name__ == '__main__':
    unittest.main()
