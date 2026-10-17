"""Frame-upload API. Phone/simulation use the same POST /predict contract."""
import io
import json
import math
import threading
from collections import deque
from time import time
from fastapi import Request
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from .schemas import PredictionResponse, HealthResponse
from .hybrid import HybridClassifier
from .preview import prediction_preview, ALLOWED_EXERCISES
from .vision_fallback import VisionFallback, settings as vision_settings

def create_app(classifier_factory=HybridClassifier, vision_factory=VisionFallback):
    lock = threading.Lock()
    recent_predictions = deque(maxlen=30)
    @asynccontextmanager
    async def lifespan(app):
        app.state.model = classifier_factory()
        app.state.vision = vision_factory()
        recent_predictions.clear()
        try:
            yield
        finally:
            app.state.model.close()
            app.state.vision.close()
    app = FastAPI(lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=Path(__file__).with_name("web") / "static"), name="static")

    @app.get('/', response_class=HTMLResponse)
    def home():
        return (Path(__file__).with_name('web') / 'index.html').read_text()

    @app.get('/health', response_model=HealthResponse)
    def health():
        return {'ready': True, 'device': app.state.model.device, 'cloud_configured': vision_settings().enabled}

    @app.post('/predict', response_model=PredictionResponse, response_model_exclude_unset=True)
    def predict(request: Request, file: UploadFile = File(...)):
        payload = file.file.read(8*1024*1024+1)
        if len(payload) > 8*1024*1024:
            raise HTTPException(413, 'Frame too large (8 MB maximum)')
        try:
            image = Image.open(io.BytesIO(payload))
            if image.width * image.height > 20_000_000:
                raise HTTPException(413, 'Image resolution too large')
            image = image.convert('RGB')
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(400, 'Upload a valid JPEG or PNG frame')
        with lock:
            session_id = request.headers.get("X-Movement-Session")
            if session_id and (len(session_id) > 80 or not all(c.isalnum() or c == "-" for c in session_id)):
                raise HTTPException(400, "Invalid movement session")
            # Namespace by client as well as opaque per-start identifier.
            key = (request.client.host, session_id) if session_id else None
            result = app.state.model.predict(image, session_id=key)
        # Cloud work runs in a bounded background executor, outside the ML lock.
        result.update(app.state.vision.update(key,image,local_exercise=result['exercise']))
        if result['exercise'] not in ALLOWED_EXERCISES | {'unknown'}:
            result['preview_discarded']=True
            result['exercise']='unknown'
            result.pop('display_name',None)
            result.pop('cloud_confirmed',None)
            if result.get('source')=='openai_vision':
                result.update(source='unknown',cloud_status='uncertain',cloud_checks=0)
        result.update(prediction_preview(result))
        ranking = sorted(result.get('scores', {}).items(), key=lambda x: x[1], reverse=True)[:3]
        with lock:
            recent_predictions.append({'time': time(), 'exercise': result['exercise'], 'raw_label': result.get('raw_label'), 'score': result.get('score'), 'top3': ranking, 'source': result.get('source'), 'movement': result.get('movement'), 'pose_features': result.get('pose_features'), 'pose_ms': result.get('pose_ms'), 'crop_label': result.get('crop_label'), 'crop_score': result.get('crop_score'), 'inference_ms': result.get('inference_ms'), 'cloud_status': result.get('cloud_status'), 'cloud_checks': result.get('cloud_checks'), 'cloud_error': result.get('cloud_error')})
        response = {"exercise": result["exercise"]}
        for name in ('display_name','source','cloud_status','cloud_checks','cloud_confirmed','preview_label','preview_score','preview_source'):
            if name in result and (key or name == 'display_name'):response[name]=result[name]
        return response

    @app.post('/capture/features')
    def capture_features(exercise: str = Form(...), timestamps: str = Form(...), files: list[UploadFile] = File(...)):
        from .capture import METRICS, extract_pose_features, summarize
        if exercise not in METRICS:
            raise HTTPException(400, 'Select a supported known exercise')
        try:
            times = json.loads(timestamps)
            if not isinstance(times, list) or len(times) != len(files) or not 3 <= len(times) <= 90:
                raise ValueError()
            if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times): raise ValueError()
            if any(b <= a for a,b in zip(times,times[1:])) or times[-1] > 10000: raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(400, 'Provide 3–90 ordered frame timestamps within 10 seconds')
        images = []
        total = 0
        try:
            # Validate the entire batch before invoking the model. Never write media to disk.
            for upload in files:
                payload = upload.file.read(1024*1024+1)
                total += len(payload)
                if len(payload) > 1024*1024 or total > 24*1024*1024:
                    raise HTTPException(413, 'Capture too large (1 MB per frame, 24 MB total)')
                try:
                    with Image.open(io.BytesIO(payload)) as image:
                        if image.format not in ('JPEG','PNG'): raise ValueError()
                        if image.width*image.height > 2_000_000: raise HTTPException(413, 'Capture frame resolution too large')
                        images.append(image.convert('RGB'))
                except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
                    raise HTTPException(400, 'Capture contains an empty, unsupported or corrupt frame')
            frames = []
            with lock:
                for image, timestamp in zip(images,times):
                    try:
                        poses = app.state.model.pose.landmarks(image)
                    except Exception:
                        raise HTTPException(503, 'Local pose extraction failed. Please try capturing again.') from None
                    frames.append(extract_pose_features(poses,image.width,image.height,timestamp,exercise))
            return summarize(exercise,frames)
        finally:
            for image in images: image.close()
            for upload in files: upload.file.close()

    @app.get('/diagnostics')
    def diagnostics(request: Request):
        if request.client.host not in ('127.0.0.1', '::1', 'testclient'):
            raise HTTPException(403, 'Local diagnostics only')
        with lock:
            return {'recent': list(recent_predictions)}

    return app


app = create_app()
