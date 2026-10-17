import Foundation
import Security

struct RecognitionResponse: Decodable {
    let exercise: String
    let display_name: String?
    let source: String?
    let cloud_status: String?
    let cloud_checks: Int?
    let cloud_confirmed: Bool?
    let preview_label: String?
    let preview_score: Double?
    let preview_source: String?
}

struct RecognitionHistory {
    private static func displayName(_ value: String) -> String? {
        let names = ["squat":"Squat", "pushup":"Push-up", "push up":"Push-up", "push-up":"Push-up",
                     "lateral_raise":"Lateral raise", "lateral raise":"Lateral raise", "lateral raises":"Lateral raise"]
        return names[value.lowercased()]
    }
    /// Readings that must all agree before the exercise label locks.
    static let lockWindow = 3
    private var labels: [String] = []
    private(set) var confidence: Double = 0
    private(set) var isLocked = false
    private(set) var cloudConfirmed = false
    private(set) var candidate = "Unknown"
    private(set) var previewLabel = "Unknown"
    private(set) var previewScore: Double?
    private(set) var previewSource: String?
    var sampleCount: Int { labels.count }
    var agreeingCount: Int { cloudConfirmed ? 2 : Int((confidence * Double(Self.lockWindow)).rounded()) }

    mutating func reset() {
        labels = []; confidence = 0; isLocked = false; cloudConfirmed = false; candidate = "Unknown"
        previewLabel = "Unknown"; previewScore = nil; previewSource = nil
    }
    mutating func apply(_ result: RecognitionResponse) -> String {
        guard !isLocked else { return candidate }
        if result.cloud_confirmed == true, result.source == "openai_vision", result.cloud_checks == 2,
           let name = Self.displayName(result.exercise),
           let supplied = result.display_name.flatMap(Self.displayName), supplied == name {
            candidate = name; cloudConfirmed = true; confidence = 1; isLocked = true
            previewLabel = name; previewScore = nil; previewSource = "openai_vision"
            return candidate
        }
        let accepted = update(result.exercise)
        let validName = result.preview_label.flatMap(Self.displayName)
        previewLabel = isLocked ? candidate : (result.preview_label == nil ? accepted : (validName ?? "Unknown"))
        previewSource = ["image", "person_crop", "movement"].contains(result.preview_source ?? "") ? result.preview_source : nil
        if let score = result.preview_score, score.isFinite, (0...1).contains(score),
           previewSource == "image" || previewSource == "person_crop",
           validName == previewLabel {
            previewScore = score
        } else { previewScore = nil }
        return accepted
    }
    mutating func update(_ value: String) -> String {
        guard !isLocked else { return candidate }
        let current = Self.displayName(value) ?? "Unknown"
        labels.append(current)
        labels = Array(labels.suffix(Self.lockWindow))
        let counts = Dictionary(grouping: labels.filter { $0 != "Unknown" }, by: { $0 }).mapValues(\.count)
        let best = counts.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.first
        candidate = best?.key ?? "Unknown"
        confidence = Double(best?.value ?? 0) / Double(Self.lockWindow)
        isLocked = labels.count == Self.lockWindow && confidence >= 1 && current == candidate && candidate != "Unknown"
        return candidate
    }
}

enum RecognitionRequest {
    static func make(endpoint: URL, jpeg: Data, sessionID: String? = nil) -> URLRequest {
        let boundary = UUID().uuidString
        var body = Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".utf8)
        body.append(jpeg)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        var request = URLRequest(url: endpoint, timeoutInterval: 30)
        request.httpMethod = "POST"
        if let sessionID { request.setValue(sessionID, forHTTPHeaderField: "X-Movement-Session") }
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        return request
    }
}

// Trust is anchored to the bundled demo CA and evaluated for the exact configured
// hostname. Redirects are rejected, so frames cannot be forwarded to another host.
final class PinnedTrust: NSObject, URLSessionDelegate, URLSessionTaskDelegate, @unchecked Sendable {
    let host: String
    let certificateURL: URL?
    init(host: String, certificateURL: URL? = Bundle.main.url(forResource: "move-demo-ca", withExtension: "cer")) {
        self.host = host
        self.certificateURL = certificateURL
    }
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              challenge.protectionSpace.host == host,
              let trust = challenge.protectionSpace.serverTrust,
              let url = certificateURL,
              let data = try? Data(contentsOf: url),
              let cert = SecCertificateCreateWithData(nil, data as CFData) else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        SecTrustSetPolicies(trust, SecPolicyCreateSSL(true, host as CFString))
        SecTrustSetAnchorCertificates(trust, [cert] as CFArray)
        SecTrustSetAnchorCertificatesOnly(trust, true)
        guard SecTrustEvaluateWithError(trust, nil) else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
