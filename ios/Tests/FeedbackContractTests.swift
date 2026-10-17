import Foundation

@main struct FeedbackContractTests {
    static func main() throws {
        var start = FeedbackSnapshot(phase: .start)
        start.kneeLeftDeg = 171
        var peak = FeedbackSnapshot(phase: .peak)
        peak.kneeLeftDeg = 112
        peak.torsoInclinationDeg = 49
        let finish = FeedbackSnapshot(phase: .finish)
        let input = FeedbackRequest(exercise: "squat", cameraAngleDeg: 90, snapshots: [start, peak, finish])
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(input)
        let body = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        precondition(body["exercise"] as? String == "squat")
        precondition(body["camera_angle_deg"] as? Double == 90)
        precondition(body["id"] == nil)
        let stages = body["snapshots"] as! [[String: Any]]
        precondition(stages.map { $0["phase"] as! String } == ["start", "peak", "finish"])
        precondition(stages[1]["knee_left_deg"] as? Double == 112)
        precondition(stages[1]["torso_inclination_deg"] as? Double == 49)

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let response = try decoder.decode(FeedbackResponse.self, from: Data(#"{"feedback":{"status":"assessable","observations":["Peak knee angle was 112°."],"cues":["Go deeper"],"spoken_text":"Go deeper."},"audio_base64":null,"audio_mime_type":null,"audio_error":"Speech unavailable"}"#.utf8))
        precondition(response.feedback.cues == ["Go deeper"])
        precondition(response.feedback.spokenText == "Go deeper.")
        precondition(response.audioBase64 == nil && response.audioError == "Speech unavailable")
        // One actual image remains one capture, with clockwise floor angles
        // converted into the signed server convention (270° → -90°).
        let featureJSON = #"{"exercise":"squat","status":"features_available","measurement_space":"2d_image_plane","frames":[{"timestamp_ms":0,"features":{"knee_left_deg":{"value":112,"landmark_quality":0.95,"unavailable_reason":null},"knee_right_deg":{"value":120,"landmark_quality":0.2,"unavailable_reason":"low_landmark_confidence"}}}],"review_frame_indices":[0],"complete_repetition_verified":false}"#
        let features = try JSONDecoder().decode(MovementCaptureResult.self, from: Data(featureJSON.utf8))
        let placement = PlacementRecommendation(marker: .left, cameraHeightCM: 85, exercise: .squat, subjectHeadingDegrees: 0)
        let single = FeedbackRequest.capturedImage(features: features, placement: placement)!
        precondition(single.cameraAngleDeg == -90)
        precondition(single.snapshots.count == 1 && single.snapshots[0].phase == .capture)
        precondition(single.snapshots[0].kneeLeftDeg == 112)
        precondition(single.snapshots[0].kneeRightDeg == nil)
        let singleBody = try JSONSerialization.jsonObject(with: encoder.encode(single)) as! [String: Any]
        let singleStages = singleBody["snapshots"] as! [[String: Any]]
        precondition(singleStages.count == 1 && singleStages[0]["phase"] as? String == "capture")
        let wrongExercise = PlacementRecommendation(marker: .top, cameraHeightCM: 100, exercise: .lateralRaise, subjectHeadingDegrees: 0)
        precondition(FeedbackRequest.capturedImage(features: features, placement: wrongExercise) == nil)
        let imageRequest = ImageFeatureRequest.make(endpoint: URL(string: "https://localhost:8443/capture/image")!, exercise: "squat", jpeg: Data([1,2,3]))
        let multipart = String(decoding: imageRequest.httpBody!, as: UTF8.self)
        precondition(imageRequest.httpMethod == "POST")
        precondition(multipart.components(separatedBy: "filename=").count == 2)
        precondition(!multipart.contains("timestamps"))
        print("Feedback contract tests passed")
    }
}
