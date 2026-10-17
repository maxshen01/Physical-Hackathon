# Measurement feedback component

The current feedback service accepts the exercise type, signed horizontal camera angle, and either one capture snapshot (the integrated image flow) or three ordered start/peak/finish measurement snapshots. Never duplicate a captured image into fake movement stages or apply full-repetition depth targets to one image. The iOS measurement team owns exercise recognition, pose tracking, and angle calculation. Do not reintroduce video upload, frame extraction, or direct provider calls from the app.

Keep measurement validation and cue eligibility deterministic on the server. The OpenAI model may choose only from eligible cue IDs; validate its output before constructing displayed or spoken advice. Send only approved speech text to ElevenLabs. A failed speech request must leave written feedback available. Keep provider credentials server-side and requests to OpenAI non-stored where supported.

The provisional camera-view windows and hip-offset tolerance need measurement-team validation. Three snapshots do not establish a complete repetition; describe only the supplied measurements. Do not infer pain, injury, diagnosis, or treatment. Before presenting feedback as reliable patient guidance, obtain physiotherapist review. Keep setup and API details in the README.
