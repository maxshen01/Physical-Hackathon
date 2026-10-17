"""Shared RGB-frame classifier for datasets, video, cameras, and simulators."""
import os
from collections import deque
from pathlib import Path
from time import perf_counter
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = 'prithivMLmods/Gym-Workout-Classifier-SigLIP2'
TARGETS = {'squat': 'squat', 'push up': 'pushup', 'lateral raises': 'lateral_raise'}

class ExerciseClassifier:
    def __init__(self, device=None):
        self.device = device or ('mps' if torch.backends.mps.is_available() else 'cpu')
        local_model = PROJECT_ROOT / '.cache/model'
        model_path = os.getenv('EXERCISE_MODEL_PATH', str(local_model) if (local_model / 'model.safetensors').is_file() else MODEL_ID)
        self.processor = AutoImageProcessor.from_pretrained(model_path, use_fast=False, cache_dir=os.getenv('HF_HOME', str(PROJECT_ROOT / '.cache/huggingface')))
        self.model = AutoModelForImageClassification.from_pretrained(model_path, cache_dir=os.getenv('HF_HOME', str(PROJECT_ROOT / '.cache/huggingface'))).to(self.device).eval()

    def predict(self, image, threshold=0.65, margin=0.15):
        """Accept PIL or RGB uint8 H×W×3 numpy array. Keep all 22 classes."""
        if not isinstance(image, Image.Image):
            image = Image.fromarray(np.asarray(image, dtype=np.uint8))
        image = image.convert('RGB')
        start = perf_counter()
        inputs = self.processor(images=image, return_tensors='pt').to(self.device)
        with torch.inference_mode():
            probs = self.model(**inputs).logits.softmax(-1)[0].cpu().tolist()
        scores = {self.model.config.id2label[i]: float(p) for i, p in enumerate(probs)}
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        label, score = ranking[0]
        accepted = label in TARGETS and score >= threshold and score - ranking[1][1] >= margin
        return {'exercise': TARGETS[label] if accepted else 'unknown', 'raw_label': label,
                'score': score, 'scores': scores, 'inference_ms': (perf_counter()-start)*1000}

class StablePrediction:
    """Require agreement across recent samples; reset between sources or camera moves."""
    def __init__(self, window=5, agreement=4):
        self.history = deque(maxlen=window)
        self.agreement = agreement
    def update(self, result):
        self.history.append(result['exercise'])
        stable = len(self.history) == self.history.maxlen and sum(x == result['exercise'] for x in self.history) >= self.agreement
        return dict(result, stable=stable, stable_exercise=result['exercise'] if stable else 'unknown')
    def reset(self):
        self.history.clear()
