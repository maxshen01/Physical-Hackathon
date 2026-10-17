import AVFoundation
import SwiftUI

struct FeedbackReviewView: View {
    let input: FeedbackRequest
    let baseAddress: String

    @State private var result: FeedbackResponse?
    @State private var error: String?
    @State private var busy = false
    @State private var player: AVAudioPlayer?
    @State private var reviewTask: Task<Void, Never>?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Review \(input.exercise.replacingOccurrences(of: "_", with: " "))")
                        .font(.title2.bold())
                    Text("Feedback uses three measured stages and the camera angle. It may miss details of your movement.")
                        .foregroundStyle(.secondary)

                    Button {
                        reviewTask?.cancel()
                        reviewTask = Task { await review() }
                    } label: {
                        HStack {
                            if busy { ProgressView().tint(.white) }
                            Text(busy ? "Reviewing…" : "Review")
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(busy)

                    if let error { Text(error).foregroundStyle(.red).accessibilityAddTraits(.updatesFrequently) }
                    if let result {
                        Text(result.feedback.status == "unable_to_assess" ? "Unable to assess" : "Feedback")
                            .font(.headline)
                        ForEach(result.feedback.observations, id: \.self) { Text($0) }
                        ForEach(result.feedback.cues, id: \.self) { cue in
                            Label(cue, systemImage: "checkmark.circle")
                        }
                        Text(result.feedback.spokenText).foregroundStyle(.secondary)
                        if let audioError = result.audioError {
                            Text(audioError).foregroundStyle(.secondary)
                        }
                    }

                    Text("Stop and consult your physiotherapist if the exercise causes pain or this advice conflicts with your plan.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
            }
            .navigationTitle("Voice feedback")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onDisappear {
            reviewTask?.cancel()
            player?.stop()
        }
    }

    @MainActor
    private func review() async {
        busy = true
        error = nil
        result = nil
        player?.stop()
        player = nil
        defer { busy = false }
        do {
            let response = try await FeedbackService.send(input, baseAddress: baseAddress)
            try Task.checkCancellation()
            result = response
            if let encoded = response.audioBase64, response.audioMimeType == "audio/mpeg",
               let audio = Data(base64Encoded: encoded) {
                do {
                    try AVAudioSession.sharedInstance().setCategory(.playback)
                    try AVAudioSession.sharedInstance().setActive(true)
                    let player = try AVAudioPlayer(data: audio)
                    self.player = player
                    if !player.play() { error = "Audio could not play. Written feedback is available." }
                } catch {
                    self.error = "Audio could not play. Written feedback is available."
                }
            } else if response.audioBase64 != nil {
                error = "Audio could not play. Written feedback is available."
            }
        } catch is CancellationError {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }
}
