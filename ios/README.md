# Orbit native iOS app

Open `MoveCamera.xcodeproj`, scheme **MoveCamera**, iOS 17+. The app includes recognition networking, on-device camera placement, photo capture and voice feedback in one flow. Orbit's dark background, lime actions, native text and floor-mark diagram remain consistent throughout.

**Start recording → recognise exercise → recommend position → Use this position → move phone → Capture image → extract features → LLM → automatic speech.**

No saved video is created. Recognition streams bounded frames to the HTTPS server until the exercise locks. Apple Vision then estimates facing locally. Position confirmation freezes the recommendation before moving the phone. A real photo is captured, resized to ≤1280 px, uploaded for image-plane features, and discarded after review. The signed camera angle comes from the frozen floor-mark recommendation, not the phone's current preview. Moving to the recommended mark is a manual step.

One image is encoded as **one `capture` snapshot**, never duplicated into fake start/peak/finish stages. The app drops unavailable, low-quality and nonfinite measurements. The server validates the payload and cue selection. The voice screen starts its request automatically, plays the returned MP3, and offers replay/stop. An audio failure preserves the transcript. Closing the screen cancels requests and releases audio. Stopping/backgrounding clears the capture and resets the flow.

The gear menu accepts one HTTPS demo address. Leave the optional separate feedback address blank to use the combined backend. The local demo connection uses the bundled public CA with hostname validation and rejects redirects. A separate feedback service uses normal system HTTPS trust. Provider credentials are never entered in the app.

See the root [README](../README.md) for server setup, public certificate copy, build and test commands. Camera permission and local-network permission are required; no microphone or Photos-library permission is requested. **Placement options** contains height, setup mark and manual facing correction. Controls are disabled while a photo is being processed, while Stop remains available to cancel.

Test recognition, Apple Vision orientation for all eight headings, actual movement to the selected mark, capture and audible playback on a physical iPhone. Simulator build and mocked API tests cannot verify these physical steps.
