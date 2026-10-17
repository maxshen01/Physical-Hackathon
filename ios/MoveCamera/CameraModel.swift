import AVFoundation
import Foundation
import UIKit
import Security

final class CameraModel: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    let session = AVCaptureSession()
    @Published var exercise = "Unknown"
    @Published var running = false
    @Published var confidence: Double = 0
    @Published var labelLocked = false
    @Published var cloudConfirmed = false
    @Published var agreeingReadings = 0
    @Published var liveScore: Double?
    @Published var evidenceSource: String?
    @Published var lockCandidate = "Unknown"
    @Published var message = "Keep your whole body in view."
    @Published var capturing = false
    @Published var captureMessage = "Capture six seconds once positioned."
    @Published var captureResult: MovementCaptureResult?
    @Published var reviewImages: [Data] = []
    @Published var captureJSON = ""
    private var captureStarted: Double?
    private var captureExercise: String?
    private var captureFrames: [CapturedFrame] = []
    private var capturePending = false
    private var lastCaptureTime = -Double.infinity
    private let queue = DispatchQueue(label: "move.camera")
    private var configured = false
    private var active = false
    private var busy = false
    private var lastFrame = Date.distantPast
    private let context = CIContext()
    private var endpoint: URL?
    private var task: URLSessionDataTask?
    private var network: URLSession?
    private var history = RecognitionHistory()
    private var generation = 0
    private var movementSessionID = UUID().uuidString

    func start(address: String) {
        guard let base = URL(string: address.trimmingCharacters(in: .whitespacesAndNewlines)), base.scheme?.lowercased() == "https", let host = base.host else {
            message = "Enter an HTTPS laptop address."
            return
        }
        let url = base.appendingPathComponent("predict")

        AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
            guard let self else { return }
            guard allowed else { self.publish { self.message = "Allow camera access in Settings to continue." }; return }
            self.queue.async {
                guard !self.active else { return }
                do {
                    try self.configure()
                    self.history.reset()
                    self.movementSessionID = UUID().uuidString
                    self.endpoint = url
                    self.network = URLSession(configuration: .ephemeral, delegate: PinnedTrust(host: host), delegateQueue: nil)
                    self.generation += 1
                    self.active = true
                    self.session.startRunning()
                    self.publish { self.exercise = "Unknown"; self.confidence = 0; self.labelLocked = false; self.cloudConfirmed = false; self.agreeingReadings = 0; self.liveScore = nil; self.evidenceSource = nil; self.lockCandidate = "Unknown"; self.running = true; self.message = "Move slowly. Keep your whole body in view." }
                } catch { self.publish { self.message = error.localizedDescription } }
            }
        }
    }

    func stop() {
        queue.async {
            self.cancelCapture()
            self.active = false
            self.generation += 1
            self.busy = false
            self.task?.cancel()
            self.network?.invalidateAndCancel()
            self.network = nil
            self.history.reset()
            if self.session.isRunning { self.session.stopRunning() }
            self.publish { self.running = false; self.exercise = "Unknown"; self.confidence = 0; self.labelLocked = false; self.cloudConfirmed = false; self.agreeingReadings = 0; self.liveScore = nil; self.evidenceSource = nil; self.lockCandidate = "Unknown"; self.message = "Camera stopped." }
        }
    }

    func reclassify() {
        queue.async {
            guard self.active else { return }
            self.cancelCapture()
            self.generation += 1
            self.task?.cancel()
            self.busy = false
            self.lastFrame = .distantPast
            self.history.reset()
            self.movementSessionID = UUID().uuidString
            self.publish {
                self.exercise = "Unknown"; self.confidence = 0; self.labelLocked = false; self.cloudConfirmed = false; self.agreeingReadings = 0; self.liveScore = nil; self.evidenceSource = nil; self.lockCandidate = "Unknown"
                self.message = "Keep moving until the bar turns green."
            }
        }
    }

    func clearCapture() {
        captureResult = nil; reviewImages = []; captureJSON = ""
    }

    func captureMovement() {
        queue.async {
            let names = ["Squat": "squat", "Push-up": "pushup", "Lateral raise": "lateral_raise"]
            guard self.active, self.history.isLocked, !self.capturePending,
                  let exercise = names[self.history.candidate] else { return }
            self.generation += 1
            self.task?.cancel(); self.busy = false
            self.capturePending = true
            self.captureStarted = ProcessInfo.processInfo.systemUptime
            self.lastCaptureTime = -Double.infinity
            self.captureExercise = exercise; self.captureFrames = []
            let token = self.generation
            self.publish { self.clearCapture(); self.capturing = true; self.captureMessage = "Capturing movement · 0 / 6 seconds" }
            self.queue.asyncAfter(deadline: .now() + 6) {
                guard self.active, token == self.generation, self.capturePending else { return }
                self.submitCapture(token: token)
            }
        }
    }

    private func cancelCapture() {
        captureStarted = nil; captureExercise = nil; captureFrames = []; capturePending = false
        publish { self.capturing = false; self.clearCapture(); self.captureMessage = "Capture six seconds once positioned." }
    }

    private func submitCapture(token: Int) {
        captureStarted = nil
        let frames = captureFrames
        captureFrames = []
        guard frames.count >= 3, let exercise = captureExercise, let endpoint,
              let request = try? MovementCaptureRequest.make(endpoint: endpoint.deletingLastPathComponent().appendingPathComponent("capture/features"), exercise: exercise, frames: frames) else {
            capturePending = false
            publish { self.capturing = false; self.captureMessage = "Too few camera frames. Please capture again." }
            return
        }
        publish { self.captureMessage = "Extracting features from \(frames.count) frames…" }
        task = network?.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }
            self.queue.async {
                guard self.active, token == self.generation else { return }
                self.capturePending = false; self.captureExercise = nil
                guard error == nil, let data, let response = response as? HTTPURLResponse,
                      response.statusCode == 200,
                      let result = try? JSONDecoder().decode(MovementCaptureResult.self, from: data),
                      result.frames.count == frames.count,
                      result.review_frame_indices.allSatisfy({ frames.indices.contains($0) }) else {
                    self.publish { self.capturing = false; self.captureMessage = "Feature extraction failed. Check the server and Wi-Fi, then capture again." }
                    return
                }
                let images = result.review_frame_indices.map { frames[$0].jpeg }
                let json = (try? JSONSerialization.jsonObject(with: data)).flatMap { try? JSONSerialization.data(withJSONObject: $0, options: [.prettyPrinted, .sortedKeys]) }.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                self.publish {
                    self.capturing = false; self.captureResult = result; self.reviewImages = images; self.captureJSON = json
                    self.captureMessage = result.status == "features_available" ? "Features extracted · \(result.frames.count) frames" : "Unable to extract features. Check body visibility and capture again."
                }
            }
        }
        task?.resume()
    }

    private func configure() throws {
        guard !configured else { return }
        guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw NSError(domain: "MoveCamera", code: 1, userInfo: [NSLocalizedDescriptionKey: "No rear camera is available."])
        }
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .hd1280x720
        let input = try AVCaptureDeviceInput(device: camera)
        guard session.canAddInput(input) else { throw NSError(domain: "MoveCamera", code: 2, userInfo: [NSLocalizedDescriptionKey: "Could not open the camera."]) }
        session.addInput(input)
        let output = AVCaptureVideoDataOutput()
        output.alwaysDiscardsLateVideoFrames = true
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(output) else { session.removeInput(input); throw NSError(domain: "MoveCamera", code: 3, userInfo: [NSLocalizedDescriptionKey: "Could not read camera frames."]) }
        session.addOutput(output)
        if let connection = output.connection(with: .video), connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 }
        configured = true
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        if capturePending {
            guard let started = captureStarted, let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
            let elapsed = ProcessInfo.processInfo.systemUptime - started
            guard elapsed < 6, elapsed-lastCaptureTime >= 0.1, captureFrames.count < 60 else { return }
            let image = CIImage(cvPixelBuffer: buffer)
            let scale = min(1, 640 / max(image.extent.width, image.extent.height))
            let resized = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
            guard let cgImage = context.createCGImage(resized, from: resized.extent),
                  let jpeg = UIImage(cgImage: cgImage).jpegData(compressionQuality: 0.85) else { return }
            lastCaptureTime = elapsed
            captureFrames.append(CapturedFrame(timestamp: elapsed*1000, jpeg: jpeg))
            publish { self.captureMessage = String(format: "Capturing movement · %.1f / 6 seconds", elapsed) }
            return
        }
        guard active, !history.isLocked, !busy, Date().timeIntervalSince(lastFrame) >= 0.5,
              let endpoint, let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let image = CIImage(cvPixelBuffer: buffer)
        let scale = min(1, 640 / max(image.extent.width, image.extent.height))
        let resized = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        guard let cgImage = context.createCGImage(resized, from: resized.extent),
              let jpeg = UIImage(cgImage: cgImage).jpegData(compressionQuality: 0.85) else { return }
        busy = true
        lastFrame = Date()
        let token = generation
        let request = RecognitionRequest.make(endpoint: endpoint, jpeg: jpeg, sessionID: movementSessionID)
        task = network?.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }
            self.queue.async {
                guard token == self.generation, self.active else { return }
                self.busy = false
                guard error == nil, let data, let response = response as? HTTPURLResponse, response.statusCode == 200,
                      let result = try? JSONDecoder().decode(RecognitionResponse.self, from: data) else {
                    let display = self.history.update("unknown")
                    let confidence = self.history.confidence
                    let agreeing = self.history.agreeingCount
                    self.publish { self.exercise = "Unknown"; self.liveScore = nil; self.evidenceSource = nil; self.confidence = confidence; self.lockCandidate = display; self.agreeingReadings = agreeing; self.message = "Cannot reach recognition. Check the laptop address and Wi-Fi." }
                    return
                }
                let display = self.history.apply(result)
                let confidence = self.history.confidence
                let locked = self.history.isLocked
                let cloud = self.history.cloudConfirmed
                let agreeing = self.history.agreeingCount
                let preview = self.history.previewLabel
                let score = self.history.previewScore
                let evidence = self.history.previewSource
                self.publish {
                    self.exercise = locked ? display : preview; self.liveScore = score; self.evidenceSource = evidence; self.lockCandidate = display; self.confidence = confidence; self.labelLocked = locked; self.cloudConfirmed = cloud; self.agreeingReadings = agreeing
                    if locked {
                        self.message = cloud ? "Two AI checks agree. Label fixed until Re-classify." : "Label fixed for this session. Tap Re-classify to check again."
                    } else {
                        switch result.cloud_status {
                        case "checking": self.message = "Still uncertain locally. AI is checking a short movement sequence…"
                        case "awaiting_fresh_frames", "checking_again": self.message = "First AI check complete. Keep moving for a second check…"
                        case "disagreement", "uncertain": self.message = "AI could not confirm one exercise. Local classification continues."
                        case "error": self.message = "AI check unavailable. Local classification continues."
                        case "budget_reached": self.message = "AI request limit reached. Local classification continues."
                        default: self.message = "Keep moving until the bar turns green."
                        }
                    }
                }
            }
        }
        task?.resume()
    }

    private func publish(_ action: @escaping @Sendable () -> Void) { DispatchQueue.main.async(execute: action) }
}
