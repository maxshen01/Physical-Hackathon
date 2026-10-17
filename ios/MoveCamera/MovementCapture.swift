import Foundation

struct CapturedFrame {
    let timestamp: Double
    let jpeg: Data
}

struct MovementCaptureResult: Decodable {
    struct Measurement: Decodable {
        let value: Double?
        let landmark_quality: Double?
        let unavailable_reason: String?
    }
    struct FeatureRange: Decodable {
        let min: Double?
        let max: Double?
        let min_timestamp_ms: Double?
        let max_timestamp_ms: Double?
        let valid_frames: Int
        let total_frames: Int
    }
    let ranges: [String: FeatureRange]?
    struct Frame: Decodable {
        let timestamp_ms: Double
        let features: [String: Measurement]
    }
    let exercise: String
    let status: String
    let measurement_space: String
    let frames: [Frame]
    let review_frame_indices: [Int]
    let complete_repetition_verified: Bool
}

enum MovementCaptureRequest {
    static func make(endpoint: URL, exercise: String, frames: [CapturedFrame]) throws -> URLRequest {
        let boundary = UUID().uuidString
        var body = Data()
        func append(_ text: String) { body.append(Data(text.utf8)) }
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"exercise\"\r\n\r\n\(exercise)\r\n")
        let timestamps = try JSONEncoder().encode(frames.map(\.timestamp))
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"timestamps\"\r\n\r\n")
        body.append(timestamps); append("\r\n")
        for frame in frames {
            append("--\(boundary)\r\nContent-Disposition: form-data; name=\"files\"; filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n")
            body.append(frame.jpeg); append("\r\n")
        }
        append("--\(boundary)--\r\n")
        var request = URLRequest(url: endpoint, timeoutInterval: 60)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        return request
    }
}

enum ImageFeatureRequest {
    static func make(endpoint: URL, exercise: String, jpeg: Data) -> URLRequest {
        let boundary = UUID().uuidString
        var body = Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"exercise\"\r\n\r\n\(exercise)\r\n".utf8)
        body.append(Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"capture.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".utf8))
        body.append(jpeg)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        var request = URLRequest(url: endpoint, timeoutInterval: 45)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        return request
    }
}

extension FeedbackRequest {
    static func capturedImage(features: MovementCaptureResult, placement: PlacementRecommendation) -> FeedbackRequest? {
        guard features.exercise == placement.exercise.rawValue,
              features.measurement_space == "2d_image_plane", features.frames.count == 1,
              !features.complete_repetition_verified else { return nil }
        let values = features.frames[0].features
        func value(_ key: String) -> Double? {
            guard let measurement = values[key], measurement.unavailable_reason == nil,
                  let quality = measurement.landmark_quality, quality.isFinite, quality >= 0.6,
                  let value = measurement.value, value.isFinite else { return nil }
            return value
        }
        var snapshot = FeedbackSnapshot(phase: .capture)
        switch placement.exercise {
        case .squat:
            snapshot.kneeLeftDeg = value("knee_left_deg")
            snapshot.kneeRightDeg = value("knee_right_deg")
            snapshot.torsoInclinationDeg = value("torso_inclination_deg")
        case .pushup:
            snapshot.elbowLeftDeg = value("elbow_left_deg")
            snapshot.elbowRightDeg = value("elbow_right_deg")
            snapshot.bodyAlignmentLeftDeg = value("body_alignment_left_deg")
            snapshot.bodyAlignmentRightDeg = value("body_alignment_right_deg")
            snapshot.hipOffsetLeftTorsoLengths = value("hip_offset_left_torso_lengths")
            snapshot.hipOffsetRightTorsoLengths = value("hip_offset_right_torso_lengths")
        case .lateralRaise:
            snapshot.armLeftDeg = value("arm_left_deg")
            snapshot.armRightDeg = value("arm_right_deg")
            snapshot.armDifferenceDeg = value("arm_difference_deg")
        }
        let clockwise = Double(placement.approximateCameraAngleDegrees)
        let signed = clockwise > 180 ? clockwise - 360 : clockwise
        return FeedbackRequest(exercise: placement.exercise.rawValue, cameraAngleDeg: signed, snapshots: [snapshot])
    }
}
