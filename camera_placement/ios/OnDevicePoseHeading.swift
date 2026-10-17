import AVFoundation
import Vision

/// Apple Vision runs on the phone. No camera frame leaves this component.
final class OnDevicePoseHeading {
    private let request = VNDetectHumanBodyPose3DRequest()

    func estimate(_ buffer: CVPixelBuffer, exercise: PlacementExercise, setupMarker: FloorMarker) -> Double? {
        do {
            let handler = VNImageRequestHandler(cvPixelBuffer: buffer, orientation: .up, options: [:])
            try handler.perform([request])
            guard let observation = request.results?.first else { return nil }
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
            if exercise == .pushup {
                let head = try observation.cameraRelativePosition(.centerHead).columns.3
                let root = try observation.cameraRelativePosition(.root).columns.3
                // Camera coordinates have +z toward the camera; the floor
                // selector uses +z away from the camera.
                vector = FloorVector(xRight: Double(head.x - root.x), zAway: Double(root.z - head.z))
                guard hypot(vector.xRight, vector.zAway) > 0.25 else { return nil }
            } else {
                let left = try observation.cameraRelativePosition(.leftShoulder).columns.3
                let right = try observation.cameraRelativePosition(.rightShoulder).columns.3
                let shoulderX = Double(left.x - right.x)
                let shoulderZ = Double(left.z - right.z)
                guard hypot(shoulderX, shoulderZ) > 0.15 else { return nil }
                // Anatomical left-minus-right shoulder axis rotated toward
                // the person's front in the camera's horizontal plane.
                vector = FloorVector(xRight: -shoulderZ, zAway: -shoulderX)
            }
            return PoseHeading.floorHeading(from: vector, setupMarker: setupMarker)
        } catch {
            return nil
        }
    }
}
