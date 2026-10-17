// Runs the native app's actual TLS, multipart, decoding, and label stabilisation code.
import Foundation

struct ReplayClip: Codable { let name: String; let expected: String; let subject: String; let url: String; let frames: [String] }
struct FrameResult: Codable { let frame: Int; let raw: String; let display: String; let elapsedMS: Double }
struct ClipResult: Codable { let name: String; let subject: String; let expected: String; let source: String; let totalFrames: Int; let correctRaw: Int; let correctDisplay: Int; let wrongDisplay: Int; let firstCorrectSeconds: Double?; let majorityDisplay: String; let frames: [FrameResult] }
struct ReplayReport: Codable { let displayPolicy: String; let endpoint: String; let samplesPerSecond: Int; let transport: String; let clips: [ClipResult] }

@main struct Replay {
    static func main() async throws {
        let args = CommandLine.arguments
        guard args.count == 5, let endpoint = URL(string: args[2]), let host = endpoint.host else { fatalError("manifest endpoint CA output") }
        // Meaningful app-state checks before using the real network.
        var state = RecognitionHistory()
        for _ in 0..<8 { _ = state.update("squat") }
        precondition(!state.isLocked)
        _ = state.update("unknown")
        precondition(state.update("squat") == "Squat" && state.isLocked)
        precondition(state.update("unknown") == "Squat")
        precondition(state.update("pushup") == "Squat")
        state.reset()
        precondition(!state.isLocked && state.confidence == 0)
        precondition(state.update("unrecognised_label") == "Unknown")
        let clips = try JSONDecoder().decode([ReplayClip].self, from: Data(contentsOf: URL(fileURLWithPath: args[1])))
        let network = URLSession(configuration: .ephemeral, delegate: PinnedTrust(host: host, certificateURL: URL(fileURLWithPath: args[3])), delegateQueue: nil)
        defer { network.invalidateAndCancel() }
        var results: [ClipResult] = []
        let names = ["squat":"Squat", "pushup":"Push-up", "lateral_raise":"Lateral raise", "unknown":"Unknown"]
        for clip in clips {
            let sessionID = UUID().uuidString
            var state = RecognitionHistory(), frames: [FrameResult] = []
            let expected = names[clip.expected] ?? "Unknown"
            for (i, path) in clip.frames.enumerated() {
                let jpeg = try Data(contentsOf: URL(fileURLWithPath:path))
                let start = Date()
                let (data,response) = try await network.data(for: RecognitionRequest.make(endpoint:endpoint,jpeg:jpeg,sessionID:sessionID))
                guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw NSError(domain:"Replay", code:1,userInfo:[NSLocalizedDescriptionKey:"Non-200 classifier response"]) }
                let prediction = try JSONDecoder().decode(RecognitionResponse.self,from:data)
                let elapsed = Date().timeIntervalSince(start)
                frames.append(FrameResult(frame:i,raw:prediction.exercise,display:state.update(prediction.exercise),elapsedMS:elapsed*1000))
                if ProcessInfo.processInfo.environment["REPLAY_REALTIME"] == "1", elapsed < 0.5 {
                    try await Task.sleep(nanoseconds: UInt64((0.5-elapsed)*1_000_000_000))
                }
            }
            let counts = Dictionary(grouping:frames,by:{$0.display}).mapValues(\.count)
            let majority = counts.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.first?.key ?? "Unknown"
            let first = frames.firstIndex { $0.display == expected }
            let result = ClipResult(name:clip.name,subject:clip.subject,expected:expected,source:clip.url,totalFrames:frames.count,correctRaw:frames.filter{names[$0.raw]==expected}.count,correctDisplay:frames.filter{$0.display==expected}.count,wrongDisplay:frames.filter{$0.display != expected && $0.display != "Unknown"}.count,firstCorrectSeconds:first.map{Double($0)/2},majorityDisplay:majority,frames:frames)
            results.append(result)
            print("\(clip.name) / \(clip.subject): \(result.correctDisplay)/\(result.totalFrames) displayed correctly; majority \(majority)")
        }
        let encoder=JSONEncoder();encoder.outputFormatting=[.prettyPrinted,.sortedKeys]
        try encoder.encode(ReplayReport(displayPolicy:"90 percent of ten readings locks the first known label until reset",endpoint:args[2],samplesPerSecond:2,transport:"Native shared RecognitionRequest, PinnedTrust, RecognitionResponse, RecognitionHistory",clips:results)).write(to:URL(fileURLWithPath:args[4]))
    }
}
