# Live phone-camera demo

The phone opens the app in its browser. Its rear-camera frames are uploaded to the laptop, which runs the classifier. The screen displays only the recognised exercise: **Squat, Push-up, Lateral raise, or Unknown**, plus camera controls and connection messages. There is no recording upload or simulated input in this version.

## Laptop preparation

From the project root, install the Python requirements in `.venv` if not already installed:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r exercise_demo/requirements.txt
```

For a laptop-only check, run:

```sh
cd exercise_demo
../.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000`. Browsers permit localhost camera access. A phone's `localhost` is the phone itself, so use the HTTPS setup below for a real phone.

## HTTPS on a phone, without a public tunnel

1. Put laptop and phone on the same trusted Wi-Fi. Guest/public networks may isolate devices.
2. From the project root run:

   ```sh
   ./exercise_demo/run_phone.sh
   ```

   The launcher uses the Mac's existing OpenSSL to create a project-local demo CA and a server certificate. It does not install software or change the Mac's certificate trust. If the Wi-Fi interface isn't `en0`, supply your laptop's Wi-Fi IPv4 address:

   ```sh
   ./exercise_demo/run_phone.sh 192.168.1.42
   ```

3. In Finder press Cmd-Shift-G and open the project's `.cache/tls` directory. Transfer **only `move-demo-ca.cer`** to your phone, for example using AirDrop. This is a public certificate. Never transfer `demo-ca-key.pem`, `phone-key.pem`, or other private-key files.
4. Trust that root certificate on the phone:
   - **iPhone:** install the downloaded profile in Settings → General → VPN & Device Management. Then enable **Move Local Demo CA** in Settings → General → About → Certificate Trust Settings.
   - **Android:** use Settings → Security → Encryption & credentials → Install a certificate → CA certificate (wording varies). Use a browser that honours user-installed CAs.
5. Allow the server through the Mac firewall if prompted. Open the printed **`https://...:8443`** URL on your phone. It must load without a certificate warning. Tap **Start camera**, then allow camera access.

The server loads the configured model before it becomes ready; first startup may require downloading model weights. The phone needs to reach the laptop, but inference does not run on the phone. Re-run the script if your laptop's IP changes. It preserves the CA, so the phone does not need to install it again. The CA expires after 30 days and server certificates after 14 days. To renew an expired CA, remove `.cache/tls` and rerun, then install/trust the new public certificate on your phone.

The private keys and certificates stay inside the gitignored `.cache/tls` directory with restrictive permissions. The app serves only its HTML page and API routes, never that directory. The launcher accepts an IPv4 address; do not replace it with a hostname.

When finished, stop the server with Ctrl-C and remove the **Move Local Demo CA** profile/trust from the phone if no longer needed. No Mac root trust was installed.

## Input and output contract

`POST /predict` accepts a multipart `file` containing one JPEG or PNG frame (maximum 8 MB; maximum 20 million pixels). It returns only:

```json
{"exercise":"squat"}
```

The browser applies three-consecutive-prediction smoothing. It keeps one request in flight at a time, scales the longest frame dimension to at most 640 pixels, and waits 350 ms between completed requests. Recognition is image-based; smoothing does not establish that a full repetition happened. Stop and backgrounding the page stop camera tracks and uploads. No frames are persisted by the application code.

## Demo check

- Start camera and confirm the phone's rear camera opens.
- Stand far enough away to include hands and feet; perform each exercise.
- Try unrelated movement. Inspect whether the classifier returns Unknown rather than forcing a target label.
- Tap Stop: the phone camera indicator should turn off.
- Restart, then lock the phone or switch apps: capture should stop.
- Disconnect Wi-Fi during capture: a connection error should appear, not a stale live state.

A real phone is required to validate browser permission, certificate trust, rear-camera selection, and real-world recognition. These cannot be established by an API unit test.

## Model status

This is an experimental exercise classifier. Strong results on individual test images do not establish reliable recognition from real-life video. In the initial online-data check, no sampled UCF push-up validation clips were accepted; test your actual phone footage before relying on the demo. Unknown means the model did not accept a supported exercise, not that no exercise happened.

The HTTPS launcher uses port 8443 (override with `PHONE_PORT`) so it can run alongside the localhost preview on port 8000.

## QR pairing helper

With the HTTPS app running, start `.venv/bin/python exercise_demo/pair_phone.py --host-ip YOUR_WIFI_IP` from the workspace root. Scan `results/phone-setup-qr.png`. The helper serves a setup page and only the public CA certificate/profile on port 8001. It never serves private keys. On iPhone use Safari to download the profile, install it in Settings, enable trust, then use the page's Open exercise camera link. Stop the helper with Ctrl-C after pairing.
