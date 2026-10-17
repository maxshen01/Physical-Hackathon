import AVFoundation
import Vision

/// Apple Vision runs on the phone. No camera frame leaves this component.
final class OnDevicePoseHeading {
    private let request = VNDetectHumanBodyPose3DRequest()
    private let imageRequest = VNDetectHumanBodyPoseRequest()

    func estimate(_ buffer: CVPixelBuffer, exercise: PlacementExercise, setupMarker: FloorMarker) -> PoseDirectionEstimate? {
        do {
            let handler = VNImageRequestHandler(cvPixelBuffer: buffer, orientation: .up, options: [:])
            try handler.perform([imageRequest, request])
            guard imageRequest.results?.count == 1,
                  let imagePose = imageRequest.results?.first,
                  let observation = request.results?.first else { return nil }
            // Avoid a direction from a cropped body. Vision's 3D model needs
            // the person and limbs visible for a useful skeleton.
            let joints: [VNHumanBodyPose3DObservation.JointName] = [
                .centerHead, .leftShoulder, .rightShoulder, .leftHip, .rightHip,
                .leftAnkle, .rightAnkle
            ]
            guard joints.allSatisfy({ joint in
                guard let point = try? observation.pointInImage(joint) else { return false }
                return (0.02...0.98).contains(point.x) && (0.02...0.98).contains(point.y)
            }) else { return nil }

            let vector: FloorVector
            let source: String
            if exercise == .pushup {
                let head = try observation.cameraRelativePosition(.centerHead).columns.3
                let root = try observation.cameraRelativePosition(.root).columns.3
                // Camera coordinates have +z toward the camera; the floor
                // selector uses +z away from the camera.
                vector = FloorVector(xRight: Double(head.x - root.x), zAway: Double(root.z - head.z))
                guard hypot(vector.xRight, vector.zAway) > 0.25 else { return nil }
                source = "Apple Vision 3D head-to-hips"
            } else {
                func imagePoint(_ joint: VNHumanBodyPoseObservation.JointName) -> PoseImagePoint? {
                    guard let point = try? imagePose.recognizedPoint(joint) else { return nil }
                    return PoseImagePoint(x: point.x, y: point.y, confidence: Double(point.confidence))
                }
                guard let leftShoulder = imagePoint(.leftShoulder),
                      let rightShoulder = imagePoint(.rightShoulder),
                      let leftHip = imagePoint(.leftHip), let rightHip = imagePoint(.rightHip),
                      [leftShoulder, rightShoulder, leftHip, rightHip].allSatisfy(\.usable) else { return nil }
                let profile = TorsoOrientation.standingProfile(
                    leftShoulder: leftShoulder, rightShoulder: rightShoulder,
                    leftHip: leftHip, rightHip: rightHip,
                    nose: imagePoint(.nose), ears: [imagePoint(.leftEar), imagePoint(.rightEar)].compactMap { $0 },
                    imageAspect: Double(CVPixelBufferGetWidth(buffer)) / Double(CVPixelBufferGetHeight(buffer))
                )
                if let profile {
                    // Never fall back to a frontal 3D pose when the independent
                    // image landmarks show a profile but cannot resolve its front.
                    guard let direction = profile.xDirection else { return nil }
                    vector = FloorVector(xRight: direction, zAway: 0)
                    source = "Apple Vision 2D torso + face profile"
                } else {
                    func position(_ joint: VNHumanBodyPose3DObservation.JointName) throws -> SIMD3<Double> {
                        let point = try observation.cameraRelativePosition(joint).columns.3
                        return SIMD3(Double(point.x), Double(point.y), Double(point.z))
                    }
                    guard let front = TorsoOrientation.vector(
                        leftShoulder: try position(.leftShoulder), rightShoulder: try position(.rightShoulder),
                        leftHip: try position(.leftHip), rightHip: try position(.rightHip)
                    ) else { return nil }
                    vector = front
                    source = "Apple Vision 3D torso plane"
                }
            }
            guard let degrees = PoseHeading.floorHeading(from: vector, setupMarker: setupMarker) else { return nil }
            return PoseDirectionEstimate(degrees: degrees, source: source)
        } catch {
            return nil
        }
    }
}
