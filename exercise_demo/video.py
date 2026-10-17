"""Video file, webcam index, or phone MJPEG/RTSP URL → shared classifier."""
import argparse
import json
import time
import cv2
from classifier import ExerciseClassifier, StablePrediction

def frames(source, sample_fps=2):
    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open source: {source}')
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    stride = max(1, round(source_fps/sample_fps)) if 0 < source_fps < 240 else 1
    try:
        index = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if index % stride == 0:
                yield index, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            index += 1
    finally:
        cap.release()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, help='Video path, webcam index, MJPEG/RTSP URL')
    parser.add_argument('--output', default='predictions.jsonl')
    parser.add_argument('--sample-fps', type=float, default=2)
    args = parser.parse_args()
    model, smoother = ExerciseClassifier(), StablePrediction()
    with open(args.output, 'w') as output:
        for index, rgb in frames(args.source, args.sample_fps):
            result = smoother.update(model.predict(rgb))
            result.update(frame_index=index, timestamp_ms=int(time.time()*1000))
            output.write(json.dumps(result)+'\n')
            output.flush()
            print(result['stable_exercise'], round(result['score'], 3))
