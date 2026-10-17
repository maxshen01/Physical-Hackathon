import AVFoundation
import SwiftUI

struct ContentView: View {
    @StateObject private var camera = CameraModel()
    @AppStorage("backendAddress") private var address = "https://172.20.10.3:8443"
    @State private var settings = false
    @Environment(\.scenePhase) private var scenePhase
    private let ink = Color(red: 0.09, green: 0.14, blue: 0.11)
    private let confirmed = Color(red: 0.16, green: 0.43, blue: 0.24)

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("Kinevoa").font(.system(size: 28, weight: .bold, design: .rounded))
                Spacer()
                Button { settings = true } label: { Image(systemName: "gearshape").font(.title3) }.accessibilityLabel("Server settings")
            }
            CameraPreview(session: camera.session)
                .overlay(alignment: .topLeading) {
                    if camera.running { Text("LIVE").font(.caption.bold()).padding(9).background(Color(red: 0.73, green: 0.96, blue: 0.7), in: Capsule()).padding() }
                }
                .overlay { if !camera.running { VStack(spacing: 12) { Image(systemName: "camera").font(.largeTitle); Text("Set your phone down.\nKeep your whole body in view.").multilineTextAlignment(.center) }.foregroundStyle(.white.opacity(0.8)) } }
                .clipShape(RoundedRectangle(cornerRadius: 24))
                .frame(maxHeight: .infinity)
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(camera.labelLocked ? "EXERCISE" : "MOST LIKELY").font(.caption).tracking(2).foregroundStyle(.secondary)
                    Spacer()
                    if camera.labelLocked { Label("LOCKED", systemImage: "lock.fill").font(.caption.bold()).foregroundStyle(confirmed) }
                }
                Text(camera.exercise).font(.system(size: 48, weight: .semibold, design: .rounded)).minimumScaleFactor(0.6).lineLimit(1).accessibilityAddTraits(.updatesFrequently)
                if let score = camera.liveScore {
                    HStack {
                        Text("Model confidence").font(.subheadline).foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int((score * 100).rounded()))%")
                            .font(.system(.title3, design: .rounded).weight(.semibold)).monospacedDigit()
                            .contentTransition(.numericText())
                    }.accessibilityElement(children: .combine)
                } else if camera.evidenceSource == "movement" {
                    Text("Movement pattern confirmed").font(.subheadline).foregroundStyle(.secondary)
                } else if !camera.cloudConfirmed {
                    Text(camera.running ? (camera.evidenceSource == nil ? "Waiting for a model reading…" : "No supported exercise detected.") : "Live confidence appears when classification starts.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            VStack(alignment: .leading, spacing: 7) {
                HStack {
                    Text(camera.cloudConfirmed ? "AI cross-check" : "Session agreement").font(.subheadline)
                    Spacer()
                    Text(camera.cloudConfirmed ? "2/2" : "\(Int((camera.confidence * 100).rounded()))%")
                        .font(.system(.headline, design: .rounded)).monospacedDigit()
                        .foregroundStyle(camera.labelLocked ? confirmed : ink)
                }
                ProgressView(value: camera.confidence).tint(camera.labelLocked ? confirmed : ink.opacity(0.45))
                    .accessibilityLabel(camera.cloudConfirmed ? "AI cross-check" : "Recognition consistency")
                    .accessibilityValue(camera.cloudConfirmed ? "Two AI checks agree. Label locked." : "\(camera.agreeingReadings) of 10 readings agree. \(camera.labelLocked ? "Label locked" : "Checking")")
                Text(camera.cloudConfirmed ? "Two fresh image sequences agree · locked" : camera.lockCandidate == "Unknown" ? "No accepted label yet · locks at 90% agreement" : "\(camera.lockCandidate): \(camera.agreeingReadings)/10 agree · locks at 90%")
                    .font(.caption).foregroundStyle(.secondary)
            }
            HStack(spacing: 12) {
                Button { if camera.running { camera.reclassify() } else { camera.start(address: address) } } label: {
                    Text(camera.running ? "Re-classify" : "Start classifying").frame(maxWidth: .infinity).padding(.vertical, 16)
                }.buttonStyle(.plain).background(ink, in: RoundedRectangle(cornerRadius: 14)).foregroundStyle(.white)
                Button { camera.stop() } label: { Text("Stop").padding(16) }.buttonStyle(.plain).background(ink.opacity(0.09), in: RoundedRectangle(cornerRadius: 14)).disabled(!camera.running)
            }
            Text(camera.message).font(.footnote).foregroundStyle(.secondary).frame(minHeight: 32, alignment: .topLeading)
        }
        .padding(22).foregroundStyle(ink).background(Color(red: 0.95, green: 0.95, blue: 0.92))
        .sheet(isPresented: $settings) {
            NavigationStack { Form {
                Section("Laptop server") {
                    TextField("https://172.20.10.3:8443", text: $address).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                }
                Section("Recognition") { Text("Model confidence updates with each frame and can show an exercise below the acceptance threshold. It is a model score, not measured accuracy. Session agreement measures accepted predictions across the last 10 readings. At 90%, the label locks and classification uploads pause until you tap Re-classify. After 20 seconds without a lock, the optional AI fallback checks two separate frame sequences. Its agreement is shown as 2/2, not an accuracy percentage.") }
                Section { Text("Use the laptop’s HTTPS Wi-Fi address. Frames are sent securely to this server for recognition and are not saved by the app. If the OpenAI fallback is configured, a few recent frames may be sent to OpenAI after 20 seconds. The key stays on the laptop.") }
            }.navigationTitle("Connection").toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { camera.stop(); settings = false } } } }
        }
        .onChange(of: scenePhase) { _, phase in if phase != .active { camera.stop() } }
    }
}

private struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    func makeUIView(context: Context) -> PreviewView { let view = PreviewView(); view.preview.session = session; view.preview.videoGravity = .resizeAspect; return view }
    func updateUIView(_ uiView: PreviewView, context: Context) {}
}
private final class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    override init(frame: CGRect) { super.init(frame: frame); backgroundColor = .black }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() { super.layoutSubviews(); if let connection = preview.connection, connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 } }
}
