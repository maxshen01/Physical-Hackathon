import Foundation

@main struct SessionLockTests {
    static func main() {
        var state = RecognitionHistory()
        for _ in 0..<8 { _ = state.update("squat") }
        precondition(!state.isLocked && abs(state.confidence - 0.8) < 0.001)
        _ = state.update("unknown")
        precondition(!state.isLocked)
        precondition(state.update("squat") == "Squat")
        precondition(state.isLocked && abs(state.confidence - 0.9) < 0.001)
        for value in ["unknown", "pushup", "lateral_raise", "bad-label"] {
            precondition(state.update(value) == "Squat")
            precondition(state.isLocked && abs(state.confidence - 0.9) < 0.001)
        }
        state.reset()
        precondition(!state.isLocked && state.confidence == 0 && state.candidate == "Unknown")
        for _ in 0..<10 { _ = state.update("unknown") }
        precondition(!state.isLocked && state.confidence == 0)
        for _ in 0..<10 { _ = state.update("pushup") }
        precondition(state.isLocked && state.candidate == "Push-up")
        state.reset()
        for _ in 0..<8 { _ = state.update("squat") }
        _ = state.update("pushup"); _ = state.update("unknown")
        precondition(!state.isLocked && abs(state.confidence - 0.8) < 0.001)
        state.reset()
        for _ in 0..<9 { _ = state.update("squat") }
        _ = state.update("unknown")
        precondition(!state.isLocked, "Never lock an old majority on a current Unknown response")
        _ = state.update("squat")
        precondition(state.isLocked)
        state.reset()
        let decoder = JSONDecoder()
        let firstAI = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"lunge","display_name":"Lunge","source":"openai_vision","cloud_checks":1,"cloud_confirmed":false}"#.utf8))
        precondition(state.apply(firstAI) == "Unknown" && !state.isLocked)
        let confirmedAI = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"lunge","display_name":"Lunge","source":"openai_vision","cloud_checks":2,"cloud_confirmed":true}"#.utf8))
        precondition(state.apply(confirmedAI) == "Lunge" && state.isLocked && state.cloudConfirmed)
        precondition(state.update("unknown") == "Lunge")
        state.reset()
        let unsafeAI = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"lunge","display_name":"<script>","source":"openai_vision","cloud_checks":2,"cloud_confirmed":true}"#.utf8))
        precondition(state.apply(unsafeAI) == "Unknown" && !state.isLocked)
        state.reset()
        let unconfirmed = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"biceps_curl","display_name":"Biceps curl"}"#.utf8))
        precondition(state.apply(unconfirmed) == "Unknown" && !state.isLocked)
        state.reset()
        let provisional = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"unknown","preview_label":"Shoulder press","preview_score":0.82,"preview_source":"image"}"#.utf8))
        for _ in 0..<12 { _ = state.apply(provisional) }
        precondition(state.previewLabel == "Shoulder press" && state.previewScore == 0.82)
        precondition(!state.isLocked && state.confidence == 0, "Rejected preview scores must never count toward locking")
        let nextFrame = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"unknown","preview_label":"Squat","preview_score":0.58,"preview_source":"image"}"#.utf8))
        _ = state.apply(nextFrame)
        precondition(state.previewLabel == "Squat" && state.previewScore == 0.58, "Preview must update on every response")
        let acceptedFrame = try! decoder.decode(RecognitionResponse.self, from: Data(#"{"exercise":"squat","preview_label":"Squat","preview_score":0.87,"preview_source":"image"}"#.utf8))
        for _ in 0..<10 { _ = state.apply(acceptedFrame) }
        precondition(state.isLocked && state.previewScore == 0.87)
        _ = state.apply(provisional)
        precondition(state.previewLabel == "Squat" && state.previewScore == 0.87, "Preview freezes at lock")
        state.reset()
        precondition(state.previewLabel == "Unknown" && state.previewScore == nil)
        print("Session lock tests passed: 90% gate, Unknown rejection, fixed label, reset, new exercise")
    }
}
