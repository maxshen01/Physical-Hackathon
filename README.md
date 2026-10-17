Name
Orbit - The AI scribe that can see

Description
AI medical scribes have exploded, but they only have ears. That’s fine for talking therapies. In physiotherapy, what the clinician sees matters as much as what they hear.

Orbit is a camera that knows where to stand. It recognises the exercise, works out the one angle that actually shows the movement, and measures real joint angles from body landmarks. Then it writes the notes, combining what was said with what was measured.

Today, Orbit runs on an iPhone and tells you exactly where to put it. Next, it goes on wheels, circling the room, staying out of the clinician’s way, and catching every rep from the right side.
AI scribes gave clinicians ears. Orbit gives them eyes.


---

We built Orbit as a pipeline: recognise → position → measure → explain → speak.

- Recognise: a fine-tuned SigLIP 2 vision classifier (Hugging Face Transformers and PyTorch, served by FastAPI) identifies the exercise from live camera frames. It votes across readings before it commits to a label.
- Position: Apple Vision 2D and 3D body-pose detection works out which way the patient is facing, on the phone, and picks the best of eight camera positions for that exercise.
- Measure: MediaPipe Pose Landmarker finds the body, and our geometry code turns those landmarks into joint angles: knee depth, trunk lean, elbow bend, body line, left–right arm difference.
- Explain: an OpenAI vision model reads the frames and the measurements and returns structured feedback. That feedback is checked against a strict Pydantic schema before anything reaches the patient.
- Speak: ElevenLabs turns the approved cue into natural speech.

Built native: Swift, SwiftUI and AVFoundation on iPhone. No video is stored and API keys never leave the server.
