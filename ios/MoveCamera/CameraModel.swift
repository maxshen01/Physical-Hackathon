import AVFoundation
import Foundation
import UIKit
import Security

final class CameraModel: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate, AVCapturePhotoCaptureDelegate, @unchecked Sendable {
    enum Step { case recognise, position, capture, processing, review }
    let session = AVCaptureSession()
    @Published private(set) var step: Step = .recognise
    @Published private(set) var recommendation: PlacementRecommendation?
    @Published var reviewInput: FeedbackRequest?
    private let photoOutput = AVCapturePhotoOutput()
    private let placementPose = OnDevicePoseHeading()
    private var placementExercise: PlacementExercise?
    private var heightCM: Double = 170
    private var setupMarker: FloorMarker = .bottom
    private var facingOverride: FloorMarker?
    private var headings = HeadingWindow()
    private var placementLocked = false
    private var photoPending = false
    private var lastHeadingTime = Date.distantPast
    private var lastGoodHeading = Date.distantPast
    private var placementResult: PlacementRecommendation?

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
    private var wantsStart = false
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

        queue.async { self.wantsStart = true }
        AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
            guard let self else { return }
            guard allowed else { self.publish { self.message = "Allow camera access in Settings to continue." }; return }
            self.queue.async {
                guard self.wantsStart, !self.active else { return }
                guard (80...250).contains(self.heightCM) else {
                    self.publish { self.message = "Enter a person’s height between 80 and 250 cm in Placement options." }
                    return
                }
                do {
                    try self.configure()
                    self.resetPlacement()
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
            self.resetPlacement()
            self.active = false
            self.wantsStart = false
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
            self.resetPlacement()
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
        guard session.canAddOutput(output), session.canAddOutput(photoOutput) else { session.removeInput(input); throw NSError(domain: "MoveCamera", code: 3, userInfo: [NSLocalizedDescriptionKey: "Could not read camera frames."]) }
        session.addOutput(output)
        session.addOutput(photoOutput)
        if let connection = photoOutput.connection(with: .video), connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 }
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
        if active, history.isLocked {
            updateHeading(sampleBuffer)
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
                if self.history.isLocked, self.placementExercise == nil {
                    self.placementExercise = PlacementExercise.allCases.first { $0.title == display }
                    self.publish { self.step = .position; self.message = "Exercise recognised. Hold the phone steady to find your camera position." }
                }
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
                        self.message = "Exercise recognised. Hold steady at the setup mark to find your camera position."
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

    func configurePlacement(heightCM: Double, setupMarker: FloorMarker, facingOverride: FloorMarker?) {
        queue.async {
            guard !self.photoPending else { return }
            self.heightCM = heightCM
            self.setupMarker = setupMarker
            self.facingOverride = facingOverride
            self.headings.reset()
            self.placementResult = nil
            self.placementLocked = false
            self.lastGoodHeading = .distantPast
            self.publish {
                self.recommendation = nil
                if self.labelLocked { self.step = .position }
            }
            self.applyFacingOverride()
        }
    }

    func lockPlacement() {
        queue.async {
            guard self.active, self.placementResult != nil,
                  self.facingOverride != nil || Date().timeIntervalSince(self.lastGoodHeading) < 2 else { return }
            self.placementLocked = true
            self.publish { self.step = .capture; self.message = "Move to the highlighted mark. Keep the whole body in view, then capture an image." }
        }
    }

    func captureImage() {
        queue.async {
            guard self.active, self.placementLocked, !self.photoPending else { return }
            self.photoPending = true
            self.publish { self.step = .processing; self.message = "Capturing image…"; self.reviewInput = nil }
            self.photoOutput.capturePhoto(with: AVCapturePhotoSettings(), delegate: self)
        }
    }

    private func resetPlacement() {
        placementExercise = nil; placementResult = nil; placementLocked = false
        photoPending = false; headings.reset(); lastHeadingTime = .distantPast; lastGoodHeading = .distantPast
        publish { self.step = .recognise; self.recommendation = nil; self.reviewInput = nil }
    }

    private func applyFacingOverride() {
        guard active, let exercise = placementExercise, let facingOverride,
              let result = PlacementEngine.recommend(exercise: exercise, subjectHeightCM: heightCM,
                headingDegrees: facingOverride.angleDegrees, setupMarker: setupMarker) else { return }
        placementResult = result
        publish { self.recommendation = result; self.message = "Using corrected facing. Confirm this position before moving the phone." }
    }

    private func updateHeading(_ sampleBuffer: CMSampleBuffer) {
        guard !placementLocked, let exercise = placementExercise else { return }
        if facingOverride != nil { applyFacingOverride(); return }
        let now = Date()
        guard now.timeIntervalSince(lastHeadingTime) >= 0.45,
              let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastHeadingTime = now
        guard let heading = placementPose.estimate(buffer, exercise: exercise, setupMarker: setupMarker) else {
            if now.timeIntervalSince(lastGoodHeading) > 2 {
                headings.reset(); placementResult = nil
                publish { self.recommendation = nil; self.message = "Keep one full body visible. If facing is unclear, correct it in Placement options." }
            }
            return
        }
        lastGoodHeading = now
        guard let stable = headings.add(heading),
              let result = PlacementEngine.recommend(exercise: exercise, subjectHeightCM: heightCM,
                headingDegrees: stable, setupMarker: setupMarker) else { return }
        placementResult = result
        publish { self.recommendation = result; self.message = "Position ready. Confirm it, then move the phone." }
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        // Bound the upload in memory; never write the photo to the camera roll.
        let source = error == nil ? photo.fileDataRepresentation().flatMap(UIImage.init(data:)) : nil
        var jpeg: Data?
        if let source {
            let scale = min(1, 1280 / max(source.size.width, source.size.height))
            let format = UIGraphicsImageRendererFormat(); format.scale = 1
            jpeg = UIGraphicsImageRenderer(size: CGSize(width: source.size.width * scale, height: source.size.height * scale), format: format).jpegData(withCompressionQuality: 0.8) { _ in
                source.draw(in: CGRect(origin: .zero, size: CGSize(width: source.size.width * scale, height: source.size.height * scale)))
            }
        }
        let capturedJPEG = jpeg
        queue.async {
            guard self.active, self.photoPending else { return }
            guard let capturedJPEG, let exercise = self.placementExercise,
                  let placement = self.placementResult, let endpoint = self.endpoint,
                  let network = self.network else {
                self.photoPending = false
                self.publish { self.step = .capture; self.message = "Could not capture the image. Try again." }
                return
            }
            self.publish { self.message = "Extracting image features…"; self.reviewImages = [capturedJPEG] }
            let token = self.generation
            let request = ImageFeatureRequest.make(endpoint: endpoint.deletingLastPathComponent().appendingPathComponent("capture/image"), exercise: exercise.rawValue, jpeg: capturedJPEG)
            self.task = network.dataTask(with: request) { [weak self] data, response, error in
                guard let self else { return }
                self.queue.async {
                    guard self.active, token == self.generation else { return }
                    self.photoPending = false
                    guard error == nil, let data, let http = response as? HTTPURLResponse, http.statusCode == 200,
                          let features = try? JSONDecoder().decode(MovementCaptureResult.self, from: data),
                          let input = FeedbackRequest.capturedImage(features: features, placement: placement) else {
                        self.publish { self.step = .capture; self.reviewImages = []; self.message = "Feature extraction failed. Check the connection, keep your body in view, and capture again." }
                        return
                    }
                    self.publish { self.step = .review; self.captureResult = features; self.reviewInput = input; self.message = "Image features ready. Preparing voice feedback…" }
                }
            }
            self.task?.resume()
        }
    }

    private func publish(_ action: @escaping @Sendable () -> Void) { DispatchQueue.main.async(execute: action) }
}
