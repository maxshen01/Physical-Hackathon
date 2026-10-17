import AVFoundation
import SwiftUI

struct FeedbackReviewView: View {
    let input: FeedbackRequest
    let baseAddress: String
    var usesDemoTrust = false
    @Environment(\.dismiss) private var dismiss
    @State private var result: FeedbackResponse?
    @State private var error: String?
    @State private var busy = false
    @State private var player: AVAudioPlayer?
    @State private var retryID = 0
    private let signal = Color(red: 0.79, green: 0.98, blue: 0.10)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Image(systemName: "waveform").font(.system(size: 44)).foregroundStyle(signal)
                        .accessibilityHidden(true)
                    Text(busy ? "Preparing your voice feedback" : "Listen to your feedback")
                        .font(.title2.bold())
                    Text(input.exercise.replacingOccurrences(of: "_", with: " ").capitalized)
                        .foregroundStyle(.secondary)
                    if busy {
                        HStack(spacing: 12) {
                            ProgressView().tint(signal)
                            Text("Reviewing the image features and generating speech…")
                        }.accessibilityAddTraits(.updatesFrequently)
                    }
                    if let error {
                        Text(error).foregroundStyle(.red).accessibilityAddTraits(.updatesFrequently)
                        Button("Try again") { retryID += 1 }.buttonStyle(.bordered)
                    }
                    if let result {
                        if let player {
                            Button {
                                player.currentTime = 0
                                if !player.play() { error = "Audio could not play. The transcript is available below." }
                            } label: {
                                Label("Play voice feedback again", systemImage: "speaker.wave.2.fill")
                                    .frame(maxWidth: .infinity).padding(.vertical, 12)
                            }.buttonStyle(.borderedProminent).tint(signal).foregroundStyle(.black)
                            Button("Stop audio") { player.stop() }.buttonStyle(.bordered)
                        }
                        if let audioError = result.audioError {
                            Label("Voice feedback is unavailable. \(audioError)", systemImage: "speaker.slash")
                                .foregroundStyle(.secondary)
                            Button("Retry voice feedback") { retryID += 1 }.buttonStyle(.bordered)
                        }
                        Text(result.feedback.status == "unable_to_assess" ? "Please capture again" : "Transcript")
                            .font(.headline)
                        Text(result.feedback.spokenText)
                        DisclosureGroup("What the image showed") {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(result.feedback.observations.enumerated()), id: \.offset) { _, text in Text(text) }
                            }.padding(.top, 8)
                        }.foregroundStyle(.secondary)
                    }
                    Text("One image shows a pose, not a complete repetition. Follow your physiotherapist’s prescribed variation.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Text("Stop and consult your physiotherapist if the exercise causes pain or this feedback conflicts with your plan.")
                        .font(.footnote).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
            }
            .background(Color(red: 0.07, green: 0.08, blue: 0.10))
            .navigationTitle("Voice feedback").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .preferredColorScheme(.dark).tint(signal)
        .task(id: retryID) { await review() }
        .onDisappear {
            player?.stop(); player = nil; result = nil
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    @MainActor
    private func review() async {
        busy = true; error = nil; result = nil
        player?.stop(); player = nil
        defer { busy = false }
        do {
            let network: URLSession
            if usesDemoTrust, let host = URL(string: baseAddress.trimmingCharacters(in: .whitespacesAndNewlines))?.host {
                network = URLSession(configuration: .ephemeral, delegate: PinnedTrust(host: host), delegateQueue: nil)
            } else { network = URLSession(configuration: .ephemeral) }
            defer { network.invalidateAndCancel() }
            let response = try await FeedbackService.send(input, baseAddress: baseAddress, session: network)
            try Task.checkCancellation()
            result = response
            if let encoded = response.audioBase64, response.audioMimeType == "audio/mpeg", let audio = Data(base64Encoded: encoded) {
                do {
                    try AVAudioSession.sharedInstance().setCategory(.playback)
                    try AVAudioSession.sharedInstance().setActive(true)
                    let player = try AVAudioPlayer(data: audio)
                    self.player = player
                    if !player.play() { error = "Audio could not play. The transcript is available." }
                } catch { self.error = "Audio could not play. The transcript is available." }
            } else if response.audioBase64 != nil {
                error = "Audio could not play. The transcript is available."
            }
        } catch is CancellationError {
            return
        } catch {
            if !Task.isCancelled { self.error = error.localizedDescription }
        }
    }
}
