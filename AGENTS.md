# Physio video coach: project instructions

## Current integrated demo flow

The user revised the demo workflow on 2026-10-17: start the camera, classify the exercise, recommend the best available floor-mark angle, move the phone, capture one image, extract features, run the LLM, then speak feedback. Voice is the primary output, with a transcript available if speech fails. Treat this single-image flow as the current integration scope; the completed-video workflow below remains a future product requirement. Never fabricate start/peak/finish measurements from one image or claim that a still image verifies a repetition. Keep the safety, validation, server-side credentials and cleanup rules below.

## Purpose and first version

Build a patient-facing tool that accepts a completed video of a physiotherapy exercise and the exercise name. A Python backend analyses the movement with a vision-capable GPT model through the OpenAI API, then uses ElevenLabs to speak brief, practical feedback. In this project, "ChatGPT" means an OpenAI API model, not the ChatGPT web app. Keep the model ID configurable.

The first version analyses uploads after recording. It gives one or two form cues and does not provide live coaching, diagnose conditions, or maintain a video history. The exercise name is the only exercise metadata supplied by the patient; do not assume a particular prescribed variation when the name is ambiguous.

## Required workflow

1. Validate the upload before processing it. Reject unsupported, oversized, empty, or corrupt videos with a clear message.
2. Extract representative frames across the movement and retain their timestamps. Preserve enough context to judge the visible motion; do not treat a single frame as a complete exercise.
3. Send the exercise name and timestamped frames to a vision-capable GPT model using the OpenAI Responses API. Request a structured result and set `store: false` where supported.
4. Validate the model result before displaying it or sending any text to ElevenLabs. Synthesize only the approved `spoken_text` field.
5. Return the feedback text and playable audio. If speech generation fails, keep the validated text available and show a clear audio error.
6. Remove temporary video and extracted frames when processing finishes, including after failures.

Keep video processing, OpenAI analysis, and ElevenLabs speech generation in separate Python modules. Read provider credentials, model IDs, voice ID, and other provider settings from server-side environment variables. Never expose API keys to the browser or commit them to the repository.

## Feedback contract

Use a typed, validated result with these fields:

- `status`: `assessable` or `unable_to_assess`.
- `observations`: brief descriptions of movement actually visible in the clip, with timestamps when useful.
- `cues`: zero to two specific, actionable improvements grounded in those observations.
- `spoken_text`: a short, plain-language script consistent with the validated observations and cues.

If the person, relevant body parts, movement, or intended exercise variation cannot be judged, use `unable_to_assess`. In that case, avoid form corrections and ask for a clearer clip or clarification. Handle model refusal, incomplete output, malformed data, and provider timeouts as explicit outcomes; never pass unvalidated model text to speech generation.

## Patient safety and privacy

Describe only what the video supports. Do not infer pain, injury, diagnosis, clinical progress, joint angles, or exercise success from limited footage. Do not prescribe treatment or claim that the feedback is clinically validated. Make clear that the patient should stop and consult their physiotherapist if an exercise causes pain or the feedback conflicts with their prescribed plan.

Do not retain uploaded clips, frames, or generated audio as a user history in the first version. Clean up local temporary media promptly. `store: false` controls OpenAI response storage where supported; it does not promise zero retention by OpenAI or ElevenLabs. Document third-party data handling accurately from their current settings and terms before release.

## Verification and documentation

Test the pipeline with mocked providers for a clear clip, an unclear clip, unsupported or corrupt input, malformed or refused model output, and an ElevenLabs failure. Verify that temporary media is removed on both success and failure and that unvalidated text never reaches speech generation.

Before presenting the tool as reliable patient guidance, have a physiotherapist review a small set of representative exercise clips and the resulting feedback. Keep this root file for project-wide rules. Put setup instructions, API details, and evolving implementation notes in the README or narrower documentation.
