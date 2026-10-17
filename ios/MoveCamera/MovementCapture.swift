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
