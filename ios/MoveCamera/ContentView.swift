import AVFoundation
import SwiftUI

struct ContentView: View {
    private let signal = Color(red: 0.79, green: 0.98, blue: 0.10)
    private let panel = Color(red: 0.12, green: 0.14, blue: 0.17)
    @StateObject private var camera = CameraModel()
    /// Combined demo server on this Mac (Personal Hotspot address).
    private let address = "https://172.20.10.3:8443"
    @State private var heightText = "170"
    @State private var setupMarker: FloorMarker = .bottom
    @State private var facingOverride: FloorMarker?
    @Environment(\.scenePhase) private var scenePhase

    private var heightCM: Double { Double(heightText) ?? 0 }
    private var title: String {
        switch camera.step {
        case .recognise: camera.running ? "Let’s recognise your exercise" : "Ready when you are"
        case .position: "Find your camera position"
        case .capture: "Move the phone, then capture"
        case .processing: "Reading your image"
        case .review: "Your voice feedback"
        }
    }
    private var stepNumber: Int {
        switch camera.step {
        case .recognise: 1
        case .position: 2
        case .capture, .processing: 3
        case .review: 4
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Image("OrbitLogo").resizable().scaledToFit().frame(width: 140, height: 48)
                        .accessibilityLabel("Orbit")
                    Spacer()
                }
                HStack(spacing: 8) {
                    ForEach(Array(["Recognise", "Position", "Capture", "Listen"].enumerated()), id: \.offset) { index, name in
                        Text("\(index + 1) \(name)").font(.caption.weight(index + 1 == stepNumber ? .bold : .regular))
                            .foregroundStyle(index + 1 == stepNumber ? signal : .secondary)
                            .frame(maxWidth: .infinity)
                    }
                }.accessibilityLabel("Step \(stepNumber) of 4")
                Text(title).font(.title2.bold())
                CameraPreview(session: camera.session)
                    .frame(height: 280)
                    .overlay {
                        if !camera.running {
                            VStack(spacing: 10) {
                                Image(systemName: "camera.viewfinder").font(.largeTitle)
                                Text("Keep your whole body in view.\nStart, then perform your exercise slowly.")
                                    .multilineTextAlignment(.center)
                            }.padding().foregroundStyle(.white)
                        }
                    }
                    .overlay(alignment: .topLeading) {
                        if camera.labelLocked {
                            Label(camera.exercise, systemImage: "checkmark.circle.fill")
                                .font(.subheadline.bold()).padding(10)
                                .foregroundStyle(.black).background(signal, in: Capsule()).padding(12)
                        }
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                if camera.step == .recognise {
                    if camera.running {
                        Text(camera.exercise == "Unknown" ? "Looking for squat, push-up or lateral raise…" : "Recognising \(camera.exercise.lowercased())…")
                            .font(.headline)
                        ProgressView(value: camera.confidence).tint(signal)
                        Text("Keep moving until the exercise is recognised. No video is saved.")
                            .font(.footnote).foregroundStyle(.secondary)
                    } else {
                        Text("Recognise your exercise, position your phone, and hear a short review of your captured pose.")
                            .foregroundStyle(.secondary)
                    }
                }
                if camera.labelLocked {
                    if let result = camera.recommendation {
                        VStack(alignment: .leading, spacing: 12) {
                            Text(result.summary).font(.title3.bold())
                            Text("\(result.exercise.view) view · lens \(result.cameraHeightCM) cm above the floor")
                            if let facingOverride {
                                Text("Corrected facing: mark \(facingOverride.number) · \(facingOverride.title)")
                                    .font(.footnote).foregroundStyle(.secondary)
                            } else {
                                Text("Estimated facing: mark \(Int((result.subjectHeadingDegrees / 45).rounded()) % 8 + 1) · \(Int(result.subjectHeadingDegrees.rounded()))°")
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                            Text("Approx. camera angle: \(result.approximateCameraAngleDegrees)° clockwise from facing")
                                .font(.footnote).foregroundStyle(.secondary)
                            Text(camera.orientationSource).font(.caption).foregroundStyle(.secondary)
                            FloorMap(selected: result.marker, setup: setupMarker).frame(height: 160)
                        }.padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
                    } else {
                        Text("Hold steady at your setup mark. Keep the whole body visible while we estimate the facing direction.")
                            .foregroundStyle(.secondary)
                    }
                }
                if camera.step == .recognise || camera.step == .position {
                    DisclosureGroup("Placement options") {
                        VStack(spacing: 12) {
                            HStack {
                                Text("Person’s height")
                                Spacer()
                                TextField("170", text: $heightText).keyboardType(.decimalPad)
                                    .multilineTextAlignment(.trailing).frame(width: 70).textFieldStyle(.roundedBorder)
                                    .accessibilityLabel("Height in centimetres")
                                Text("cm")
                            }
                            Picker("Setup camera mark", selection: $setupMarker) {
                                ForEach(FloorMarker.allCases) { mark in Text("\(mark.number) · \(mark.title)").tag(mark) }
                            }
                            Picker("Person faces", selection: $facingOverride) {
                                Text("Automatic").tag(nil as FloorMarker?)
                                ForEach(FloorMarker.allCases) { mark in Text("\(mark.number) · \(mark.title)").tag(Optional(mark)) }
                            }
                            Text("Start at the selected floor mark. Correct the facing direction if the estimate is wrong.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }.padding(.top, 10)
                    }.padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
                }
                if camera.step == .processing {
                    HStack { ProgressView().tint(signal); Text(camera.message) }.padding(.vertical)
                        .accessibilityAddTraits(.updatesFrequently)
                } else {
                    Button(action: primaryAction) {
                        Text(primaryLabel).fontWeight(.semibold).frame(maxWidth: .infinity).padding(.vertical, 10)
                    }
                    .buttonStyle(.borderedProminent).tint(signal).foregroundStyle(.black)
                    .disabled((camera.step == .position && camera.recommendation == nil) || (camera.step == .recognise && camera.running))
                    if camera.step != .recognise || !camera.running {
                        Text(camera.message).font(.footnote).foregroundStyle(.secondary)
                            .accessibilityAddTraits(.updatesFrequently)
                    } else {
                        Text(camera.message).font(.footnote).foregroundStyle(.secondary)
                    }
                }
                if camera.running {
                    HStack {
                        Button("Start over") { facingOverride = nil; camera.reclassify() }
                        Spacer()
                        Button("Stop") { camera.stop() }
                    }.font(.subheadline)
                }
                Text("If an exercise causes pain or conflicts with your prescribed plan, stop and consult your physiotherapist.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(20)
        }
        .background(Color(red: 0.07, green: 0.08, blue: 0.10))
        .preferredColorScheme(.dark).tint(signal)
        .onChange(of: heightText) { _, _ in updatePlacement() }
        .onChange(of: setupMarker) { _, _ in updatePlacement() }
        .onChange(of: facingOverride) { _, _ in updatePlacement() }
        .onChange(of: scenePhase) { _, phase in if phase != .active { camera.stop() } }
        .sheet(item: $camera.reviewInput, onDismiss: {
            camera.clearCapture()
        }) { input in
            FeedbackReviewView(input: input, baseAddress: address, usesDemoTrust: true)
        }
    }

    private var primaryLabel: String {
        switch camera.step {
        case .recognise: camera.running ? "Recognising…" : "Start recording"
        case .position: "Use this position"
        case .capture: "Capture image"
        case .processing: "Processing…"
        case .review: "Capture another image"
        }
    }
    private func primaryAction() {
        switch camera.step {
        case .recognise:
            guard !camera.running else { return }
            updatePlacement(); camera.start(address: address)
        case .position: camera.lockPlacement()
        case .capture, .review: camera.captureImage()
        case .processing: break
        }
    }
    private func updatePlacement() {
        camera.configurePlacement(heightCM: heightCM, setupMarker: setupMarker, facingOverride: facingOverride)
    }
}

private struct FloorMap: View {
    let selected: FloorMarker?
    let setup: FloorMarker
    var body: some View {
        GeometryReader { geometry in
            let centre = CGPoint(x: geometry.size.width / 2, y: geometry.size.height / 2)
            let radius = min(geometry.size.width * 0.36, geometry.size.height * 0.39)
            Text("YOU").font(.caption.bold()).position(centre)
            ForEach(FloorMarker.allCases) { mark in
                Text("\(mark.number)").font(.caption.bold())
                    .foregroundStyle(selected == mark ? .black : .white)
                    .frame(width: 30, height: 30)
                    .background(selected == mark ? Color(red: 0.79, green: 0.98, blue: 0.10) : Color.gray.opacity(0.25), in: Circle())
                    .overlay { if setup == mark { Circle().stroke(.secondary, lineWidth: 1) } }
                    .position(x: centre.x + radius * mark.horizontal, y: centre.y + radius * mark.vertical)
                    .accessibilityLabel("Mark \(mark.number), \(mark.title)\(selected == mark ? ", recommended" : "")\(setup == mark ? ", setup camera" : "")")
            }
        }.accessibilityElement(children: .contain)
    }
}

private struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView(); view.preview.session = session; view.preview.videoGravity = .resizeAspect
        return view
    }
    func updateUIView(_ uiView: PreviewView, context: Context) {}
}
private final class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    override init(frame: CGRect) { super.init(frame: frame); backgroundColor = .black }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() {
        super.layoutSubviews()
        if let connection = preview.connection, connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 }
    }
}
