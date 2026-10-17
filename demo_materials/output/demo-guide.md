# Move demo guide

## Opening pitch

“Move takes a live view from your phone camera and displays an exercise name. For this prototype, we focus on squat, push-up and lateral raise, with an unknown output when the classifier cannot accept a target label. I’ll show the camera-to-label flow now.”

## 90-second live demo

| Time | Action | Words |
|---|---|---|
| 0–15s | Open the phone app. Share or mirror its screen. | “This is the live camera view from my phone.” |
| 15–25s | Tap Start camera and allow camera access. Position the phone securely. | “The participant stays fully in frame.” |
| 25–50s | Perform the most reliable rehearsed exercise. Allow the label to settle. | “Frames go to our server, and the app displays the accepted exercise name.” |
| 50–70s | Perform a second rehearsed exercise, if reliable. | “The same pipeline handles a different exercise.” |
| 70–80s | Optionally show a rehearsed unknown example. | “The system can also reject an uncertain or non-target prediction.” |
| 80–90s | Return to the deck. | “Next we’ll measure errors across people and camera views, then evaluate recognition across full movement sequences.” |

If a label is wrong, say: “That is a recognition error in this view. Testing those cases is our next step.” Do not keep repeating the action without explaining the result.

## Presenter notes

The six-slide deck takes about three to four minutes including the demo. Speaker notes are embedded in the PowerPoint.

1. Introduce the phone-to-label prototype.
2. Explain the small task: one participant and one camera.
3. Name the supported labels and the rejection output.
4. Switch to the live phone screen for 60–90 seconds.
5. Explain frame sampling, server inference and label stabilisation.
6. Close with the evaluation plan.

## Rehearsal checklist

- Confirm the server has finished loading the model before opening the app.
- Use the exact phone, browser, connection, lighting and placement planned for the demo.
- Use the working HTTPS app address supplied by the implementation session. A phone browser needs a secure context for camera access.
- Confirm the phone can reach the server. A phone's localhost points to the phone, not the laptop.
- Start and stop the camera once, then check reconnection.
- Rehearse each exercise separately. Choose the most reliable one first.
- Keep the whole participant visible, including hands and feet. Use comfortable movements and adequate space.
- Record a successful end-to-end run before presenting. Save it locally and test playback with sound off.
- Keep the app in the foreground. The current implementation stops the camera when the page becomes hidden.
- Disable distracting phone notifications and confirm screen mirroring works.

## Local server reference

From the project root, using the environment created by the implementation session:

```sh
.venv/bin/uvicorn server:app --app-dir exercise_demo --host 0.0.0.0 --port 8000
```

Check `http://localhost:8000/health` on the laptop. This starts the local server but does not create the HTTPS address required for the phone. Use the implementation session's confirmed phone-access setup.

## Fallback script

If the live connection fails after one recovery attempt:

“I'm switching to a recording of our prototype so you can see the complete flow. This is recorded footage.”

Play the local recording, narrate the actual visible result, then return to slide 5. If no recording exists, show the app screen and explain the intended flow as a walkthrough. Do not claim a successful live inference.

## Questions judges may ask

**What runs on the phone?**
The browser captures and samples camera frames. The app server runs model inference and returns a label. The browser stabilises the displayed label.

**Did you train the model?**
No. This prototype uses the pretrained `prithivMLmods/Gym-Workout-Classifier-SigLIP2` through Transformers. Our implementation connects camera capture, inference and the exercise display.

**Does it recognise movement or a pose?**
The current model classifies individual images. Sampling frames and stabilising labels reduces display changes, but does not establish that a full exercise movement occurred.

**How do you handle uncertainty?**
The server checks the winning class against the target labels, a score threshold and a margin over the runner-up. Rejected results become unknown. These settings need evaluation. Unknown is not a guarantee against false positives.

**How accurate is it?**
Use only measured results from the implementation session and name the dataset, sample size and test conditions. This deck deliberately makes no numerical accuracy claim. A dataset smoke test does not establish performance on this phone or in this room.

**Does the display always show the latest prediction?**
It waits for three consecutive matching labels before changing. During disagreement it can retain the previous displayed label. Account for this when demonstrating transitions.

**Does it move a robot or assess exercise form?**
The current demo outputs the exercise name. Robotic camera control and form assessment require additional implementation and validation.

**What happens to the images?**
The browser sends frames to the app server. The current application code does not save those frames. Avoid broader claims about infrastructure logging or end-to-end privacy.

## Evidence to add when the other session finishes

If there are useful measured results, include one precise statement in your spoken explanation: “On [dataset and split], we tested [N] independent [images or clips] and measured [metric].” Explain any overlap with training data if known. Keep phone results separate from dataset results. Do not present author-reported model scores as your own test results.

## Content basis

Prepared 17 October 2026 from the project source and the latest scope in the “Brainstorm voice-controlled camera” chat: live phone camera input and exercise name output. Implementation may continue changing during rehearsal. Recheck the app's stabilisation and connection instructions before presenting.
