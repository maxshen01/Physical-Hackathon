import AVFoundation
import Foundation
import UIKit

final class PlacementCameraModel: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate, AVCapturePhotoCaptureDelegate, @unchecked Sendable {
    let session = AVCaptureSession()
    @Published private(set) var running = false
    @Published private(set) var locked = false
    @Published private(set) var recommendation: PlacementRecommendation?
    @Published private(set) var message = "Choose an exercise and height, then start the setup camera."
    @Published private(set) var capturedPhoto: UIImage?

    private let queue = DispatchQueue(label: "kinevoa.placement.camera")
    private let pose = OnDevicePoseHeading()
    private let photoOutput = AVCapturePhotoOutput()
    private var configured = false
    private var active = false
    private var wantsStart = false
    private var isLocked = false
    private var lastPoseFrame = Date.distantPast
    private var lastGoodPose = Date.distantPast
    private var lastDirectionSample = Date.distantPast
    private var capturing = false
    private var exercise: PlacementExercise = .squat
    private var heightCM: Double = 170
    private var setupMarker: FloorMarker = .bottom
    private var facingOverride: FloorMarker?
    private var headings = HeadingWindow()
    private var currentRecommendation: PlacementRecommendation?

    func start(exercise: PlacementExercise, heightCM: Double, setupMarker: FloorMarker, facingOverride: FloorMarker?) {
        guard (80...250).contains(heightCM) else {
            message = "Enter a subject height between 80 and 250 cm."
            return
        }
        queue.async { self.wantsStart = true }
        AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
            guard let self else { return }
            guard allowed else {
                self.queue.async { self.wantsStart = false }
                self.publish { self.message = "Allow camera access in Settings to continue." }
                return
            }
            self.queue.async {
                guard self.wantsStart, !self.active else { return }
                do {
                    try self.configureCapture()
                    self.exercise = exercise
                    self.heightCM = heightCM
                    self.setupMarker = setupMarker
                    self.facingOverride = facingOverride
                    self.headings.reset()
                    self.currentRecommendation = nil
                    self.isLocked = false
                    self.lastPoseFrame = .distantPast
                    self.lastGoodPose = .distantPast
                    self.lastDirectionSample = .distantPast
                    self.capturing = false
                    self.active = true
                    self.session.startRunning()
                    self.publish {
                        self.running = true
                        self.locked = false
                        self.recommendation = nil
                        self.capturedPhoto = nil
                        self.message = "Hold the phone upright at marker \(setupMarker.number), aimed at one fully visible person."
                    }
                    self.recommendFromOverride()
                } catch {
                    self.active = false
                    self.wantsStart = false
                    self.publish { self.message = error.localizedDescription }
                }
            }
        }
    }

    func update(exercise: PlacementExercise, heightCM: Double, setupMarker: FloorMarker, facingOverride: FloorMarker?) {
        queue.async {
            self.exercise = exercise
            self.heightCM = heightCM
            self.setupMarker = setupMarker
            self.facingOverride = facingOverride
            self.headings.reset()
            self.currentRecommendation = nil
            self.isLocked = false
            self.lastGoodPose = .distantPast
            self.lastDirectionSample = .distantPast
            self.publish {
                self.locked = false
                self.recommendation = nil
                self.capturedPhoto = nil
                self.message = (80...250).contains(heightCM)
                    ? "Hold the phone upright at marker \(setupMarker.number), aimed at one fully visible person."
                    : "Enter a subject height between 80 and 250 cm."
            }
            self.recommendFromOverride()
        }
    }

    func lockPlacement() {
        queue.async {
            guard self.active, self.currentRecommendation != nil,
                  (self.facingOverride != nil || Date().timeIntervalSince(self.lastGoodPose) < 2) else { return }
            self.isLocked = true
            self.publish {
                self.locked = true
                self.message = "Move the phone to the highlighted floor mark and set the lens to the shown height."
            }
        }
    }

    func scanAgain() {
        queue.async {
            guard self.active else { return }
            self.isLocked = false
            self.facingOverride = nil
            self.currentRecommendation = nil
            self.headings.reset()
            self.lastGoodPose = .distantPast
            self.lastDirectionSample = .distantPast
            self.publish {
                self.locked = false
                self.recommendation = nil
                self.capturedPhoto = nil
                self.message = "Hold the phone at marker \(self.setupMarker.number) and scan again."
            }
        }
    }

    func capturePhoto() {
        queue.async {
            guard self.active, self.isLocked, !self.capturing else { return }
            self.capturing = true
            self.photoOutput.capturePhoto(with: AVCapturePhotoSettings(), delegate: self)
        }
    }

    func clearPhoto() {
        publish { self.capturedPhoto = nil }
    }

    func stop() {
        queue.async {
            self.wantsStart = false
            self.active = false
            self.isLocked = false
            self.currentRecommendation = nil
            self.headings.reset()
            self.capturing = false
            if self.session.isRunning { self.session.stopRunning() }
            self.publish {
                self.running = false
                self.locked = false
                self.recommendation = nil
                self.capturedPhoto = nil
                self.message = "Camera stopped. No photo was saved."
            }
        }
    }

    private func configureCapture() throws {
        guard !configured else { return }
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw NSError(domain: "Placement", code: 1, userInfo: [NSLocalizedDescriptionKey: "No rear camera is available."])
        }
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .photo
        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input) else {
            throw NSError(domain: "Placement", code: 2, userInfo: [NSLocalizedDescriptionKey: "Could not open the rear camera."])
        }
        session.addInput(input)
        let video = AVCaptureVideoDataOutput()
        video.alwaysDiscardsLateVideoFrames = true
        video.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        video.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(video), session.canAddOutput(photoOutput) else {
            session.removeInput(input)
            throw NSError(domain: "Placement", code: 3, userInfo: [NSLocalizedDescriptionKey: "Could not configure camera capture."])
        }
        session.addOutput(video)
        session.addOutput(photoOutput)
        if let connection = video.connection(with: .video), connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }
        if let connection = photoOutput.connection(with: .video), connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }
        configured = true
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let now = Date()
        guard active, !isLocked, (80...250).contains(heightCM),
              facingOverride == nil,
              now.timeIntervalSince(lastPoseFrame) >= 0.45,
              let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastPoseFrame = now
        guard let heading = pose.estimate(buffer, exercise: exercise, setupMarker: setupMarker) else {
            if now.timeIntervalSince(lastDirectionSample) > 1.3 { headings.reset() }
            if now.timeIntervalSince(lastGoodPose) > 2, currentRecommendation != nil {
                currentRecommendation = nil
                headings.reset()
                publish {
                    self.recommendation = nil
                    self.message = "Direction is unclear. Keep one full body in view and hold the phone steady."
                }
            }
            return
        }
        if now.timeIntervalSince(lastDirectionSample) > 1.3 { headings.reset() }
        lastDirectionSample = now
        guard let stableHeading = headings.add(heading),
              let result = PlacementEngine.recommend(
                exercise: exercise, subjectHeightCM: heightCM,
                headingDegrees: stableHeading, setupMarker: setupMarker
              ) else { return }
        lastGoodPose = now
        if result.marker != currentRecommendation?.marker
            || result.cameraHeightCM != currentRecommendation?.cameraHeightCM
            || result.approximateCameraAngleDegrees != currentRecommendation?.approximateCameraAngleDegrees {
            currentRecommendation = result
            publish {
                self.recommendation = result
                self.message = "Position ready. Lock it before moving the phone."
            }
        }
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let image = error == nil ? photo.fileDataRepresentation().flatMap(UIImage.init(data:)) : nil
        queue.async {
            self.capturing = false
            guard self.active, self.isLocked else { return }
            guard let image else {
                self.publish { self.message = "Could not capture the photo. Please try again." }
                return
            }
            self.publish {
                self.capturedPhoto = image
                self.message = "Photo captured on this phone. It has not been saved."
            }
        }
    }

    private func publish(_ action: @escaping @Sendable () -> Void) {
        DispatchQueue.main.async(execute: action)
    }

    private func recommendFromOverride() {
        guard active, let facingOverride,
              let result = PlacementEngine.recommend(
                exercise: exercise, subjectHeightCM: heightCM,
                headingDegrees: facingOverride.angleDegrees, setupMarker: setupMarker
              ) else { return }
        currentRecommendation = result
        publish {
            self.recommendation = result
            self.message = "Using corrected facing direction. Lock placement before moving the phone."
        }
    }
}
