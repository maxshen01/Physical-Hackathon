import Foundation

@main struct MovementCaptureTests {
    static func main() throws {
        let frames = [CapturedFrame(timestamp: 0, jpeg: Data([1,2])), CapturedFrame(timestamp: 100, jpeg: Data([3,4]))]
        let request = try MovementCaptureRequest.make(endpoint: URL(string: "https://localhost:8443/capture/features")!, exercise: "squat", frames: frames)
        precondition(request.httpMethod == "POST" && request.timeoutInterval == 60)
        let body = String(decoding: request.httpBody!, as: UTF8.self)
        precondition(body.contains("name=\"exercise\"\r\n\r\nsquat"))
        precondition(body.contains("[0,100]"))
        precondition(body.components(separatedBy: "name=\"files\"").count == 3)
        let json = #"{"exercise":"squat","status":"unable_to_extract","measurement_space":"2d_image_plane","frames":[{"timestamp_ms":0,"features":{"knee_left_deg":{"value":null,"landmark_quality":null,"unavailable_reason":"no_person"}}}],"review_frame_indices":[],"complete_repetition_verified":false}"#
        let result = try JSONDecoder().decode(MovementCaptureResult.self, from: Data(json.utf8))
        precondition(result.frames[0].features["knee_left_deg"]?.value == nil)
        precondition(!result.complete_repetition_verified)
        print("Movement capture contract tests passed")
    }
}
