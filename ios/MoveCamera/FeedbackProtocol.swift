import Foundation

enum FeedbackPhase: String, Encodable, Sendable {
    case start, peak, finish, capture
}

/// Measurements are supplied by the capture team; nil means unavailable.
struct FeedbackSnapshot: Encodable, Sendable {
    let phase: FeedbackPhase
    var kneeLeftDeg: Double? = nil
    var kneeRightDeg: Double? = nil
    var torsoInclinationDeg: Double? = nil
    var elbowLeftDeg: Double? = nil
    var elbowRightDeg: Double? = nil
    var bodyAlignmentLeftDeg: Double? = nil
    var bodyAlignmentRightDeg: Double? = nil
    var hipOffsetLeftTorsoLengths: Double? = nil
    var hipOffsetRightTorsoLengths: Double? = nil
    var armLeftDeg: Double? = nil
    var armRightDeg: Double? = nil
    var armDifferenceDeg: Double? = nil
}

struct FeedbackRequest: Encodable, Identifiable, Sendable {
    let id = UUID()
    let exercise: String
    let cameraAngleDeg: Double
    let snapshots: [FeedbackSnapshot]

    private enum CodingKeys: String, CodingKey {
        case exercise, cameraAngleDeg, snapshots
    }
}

struct FeedbackText: Decodable {
    let status: String
    let observations: [String]
    let cues: [String]
    let spokenText: String
}

struct FeedbackResponse: Decodable {
    let feedback: FeedbackText
    let audioBase64: String?
    let audioMimeType: String?
    let audioError: String?
}

enum FeedbackServiceError: LocalizedError {
    case invalidAddress
    case invalidResponse
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidAddress: return "Enter a hosted HTTPS feedback address in Settings."
        case .invalidResponse: return "The feedback service returned an invalid response."
        case .server(let message): return message
        }
    }
}

enum FeedbackService {
    static func send(_ input: FeedbackRequest, baseAddress: String, session: URLSession = .shared) async throws -> FeedbackResponse {
        let trimmed = baseAddress.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let base = URL(string: trimmed), base.scheme?.lowercased() == "https", base.host != nil else {
            throw FeedbackServiceError.invalidAddress
        }
        guard base.user == nil, base.password == nil, base.query == nil, base.fragment == nil else {
            throw FeedbackServiceError.invalidAddress
        }
        let endpoint = base.appendingPathComponent("api/feedback")
        var request = URLRequest(url: endpoint, timeoutInterval: 120)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(input)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw FeedbackServiceError.invalidResponse }
        guard http.statusCode == 200 else {
            let detail = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            throw FeedbackServiceError.server(detail?["detail"] as? String ?? "Feedback is unavailable (HTTP \(http.statusCode)).")
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let result = try? decoder.decode(FeedbackResponse.self, from: data) else {
            throw FeedbackServiceError.invalidResponse
        }
        let feedback = result.feedback
        guard ["assessable", "unable_to_assess"].contains(feedback.status),
              feedback.cues.count <= 2, feedback.observations.count <= 3,
              !feedback.spokenText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              feedback.spokenText.count <= 500,
              (feedback.status != "unable_to_assess" || feedback.cues.isEmpty),
              (feedback.cues.isEmpty || !feedback.observations.isEmpty),
              (feedback.observations + feedback.cues).allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && $0.count <= 240 }),
              (result.audioBase64 != nil || result.audioError != nil) else {
            throw FeedbackServiceError.invalidResponse
        }
        return result
    }
}
