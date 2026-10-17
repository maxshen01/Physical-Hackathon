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
        print("Feedback contract tests passed")
    }
}
