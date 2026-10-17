import AVFoundation
import SwiftUI

struct ContentView: View {
    private let signal = Color(red: 0.79, green: 0.98, blue: 0.10)
    private let panel = Color(red: 0.12, green: 0.14, blue: 0.17)
    @StateObject private var camera = CameraModel()
    /// Combined demo server on this Mac (Wi-Fi address).
    private let address = "https://10.217.1.88:8443"
    @State private var heightText = "170"
    @State private var setupMarker: FloorMarker = .bottom
    @State private var facingOverride: FloorMarker?
    @State private var choosingFacing = false
    @FocusState private var heightFocused: Bool
    @Environment(\.scenePhase) private var scenePhase

    private var heightCM: Double { Double(heightText) ?? 0 }
    private var validHeight: Bool { (80...250).contains(heightCM) }
    private var canContinue: Bool {
        switch camera.step {
        case .recognise: !camera.running && validHeight
        case .position: validHeight
        case .capture, .review: true
        case .processing: false
        }
    }
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
                    .frame(height: camera.step == .position ? 180 : 280)
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
                        }.padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
                    } else {
                        Text("Keep the phone at its starting mark. Hold the whole person in view, or choose their facing direction below.")
                            .foregroundStyle(.secondary)
                    }
                }
                if camera.step == .recognise || camera.step == .position {
                    placementControls
                }
                if camera.labelLocked {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(camera.step == .position ? "Which way is the person facing?" : "Your camera position")
                            .font(.headline)
                        if camera.step == .position {
                            Text("Tap the numbered mark the person is looking towards. This sets their direction; Orbit chooses the camera mark.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        FloorMap(selected: camera.recommendation?.marker, setup: setupMarker,
                                 facing: displayedFacing,
                                 onSelect: camera.step == .position ? { mark in heightFocused = false; facingOverride = mark } : nil)
                            .frame(height: 210)
                        HStack(spacing: 14) {
                            Label("Camera target", systemImage: "circle.fill").foregroundStyle(signal)
                            Label("Person faces", systemImage: "arrow.up").foregroundStyle(.cyan)
                        }.font(.caption)
                        Text("Outlined circle = phone’s starting mark. Numbers stay fixed on the floor.")
                            .font(.caption).foregroundStyle(.secondary)
                    }.padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
                }
                Text(camera.message).font(.footnote).foregroundStyle(.secondary)
                    .accessibilityAddTraits(.updatesFrequently)
                if camera.running {
                    if camera.step == .capture || camera.step == .review {
                        Button("Change camera position") { camera.revisePlacement() }
                    }
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
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom) { actionBar }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done") { heightFocused = false }
            }
        }
        .onChange(of: heightText) { _, _ in updatePlacement() }
        .onChange(of: setupMarker) { _, _ in updatePlacement() }
        .onChange(of: facingOverride) { _, _ in updatePlacement() }
        .onChange(of: scenePhase) { _, phase in if phase == .background { camera.stop() } }
        .sheet(isPresented: $choosingFacing) {
            NavigationStack {
                List {
                    Section {
                        Text("Choose the numbered floor mark the person is looking towards. Orbit will use it to choose the camera position.")
                            .font(.subheadline)
                    }
                    Section("Person’s facing direction") {
                        Button("Automatic · use camera detection") { facingOverride = nil; choosingFacing = false }
                        ForEach(FloorMarker.allCases) { mark in
                            Button {
                                facingOverride = mark
                                choosingFacing = false
                            } label: {
                                HStack {
                                    Text("Facing mark \(mark.number) · \(mark.title)")
                                    Spacer()
                                    if facingOverride == mark { Image(systemName: "checkmark") }
                                }.padding(.vertical, 6)
                            }
                            .accessibilityIdentifier("placement.facing.choice.\(mark.number)")
                        }
                    }
                }
                .navigationTitle("Person faces")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { choosingFacing = false }
                } }
            }.preferredColorScheme(.dark).tint(signal)
        }
        .sheet(item: $camera.reviewInput, onDismiss: {
            camera.clearCapture()
        }) { input in
            FeedbackReviewView(input: input, baseAddress: address, usesDemoTrust: true)
        }
    }

    private var displayedFacing: FloorMarker? {
        if let facingOverride { return facingOverride }
        guard let degrees = camera.recommendation?.subjectHeadingDegrees else { return nil }
        return FloorMarker(rawValue: Int((degrees / 45).rounded()) % 8)
    }

    private var placementControls: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Position setup").font(.headline)
            VStack(alignment: .leading, spacing: 6) {
                Text("Person’s height").font(.subheadline.bold())
                HStack {
                    TextField("Height", text: $heightText).keyboardType(.decimalPad)
                        .focused($heightFocused).textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Person’s height in centimetres")
                        .accessibilityIdentifier("placement.height")
                    Text("cm")
                }
                Text(validHeight ? "Used to set the camera lens height." : "Enter a height from 80 to 250 cm.")
                    .font(.caption).foregroundStyle(validHeight ? Color.secondary : .orange)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Where is the phone now?").font(.subheadline.bold())
                Text("Choose its starting floor mark, before moving it.").font(.caption).foregroundStyle(.secondary)
                Menu {
                    ForEach(FloorMarker.allCases) { mark in
                        Button("Mark \(mark.number) · \(mark.title)") { heightFocused = false; setupMarker = mark }
                    }
                } label: {
                    selectionLabel("Mark \(setupMarker.number) · \(setupMarker.title)")
                }
                .accessibilityLabel("Phone’s starting floor mark")
                .accessibilityValue("Mark \(setupMarker.number), \(setupMarker.title)")
                .accessibilityIdentifier("placement.setup")
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Which way is the person facing?").font(.subheadline.bold())
                Text("Choose the floor mark they are looking towards. Use this if Automatic is stuck or wrong.")
                    .font(.caption).foregroundStyle(.secondary)
                Button { heightFocused = false; choosingFacing = true } label: {
                    selectionLabel(facingOverride.map { "Facing mark \($0.number) · \($0.title)" } ?? "Automatic · camera detection")
                }
                .accessibilityLabel("Person’s facing direction")
                .accessibilityValue(facingOverride.map { "Mark \($0.number), \($0.title)" } ?? "Automatic")
                .accessibilityIdentifier("placement.facing")
            }
        }.padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
    }

    private func selectionLabel(_ value: String) -> some View {
        HStack {
            Text(value).multilineTextAlignment(.leading)
            Spacer(minLength: 8)
            Image(systemName: "chevron.up.chevron.down")
        }
        .foregroundStyle(.white).padding(12).frame(maxWidth: .infinity, minHeight: 48)
        .background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
        .contentShape(Rectangle())
    }

    private var actionBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !validHeight {
                Text("Enter a height from 80 to 250 cm to continue.").font(.footnote).foregroundStyle(.orange)
            } else if camera.step == .position && camera.recommendation == nil {
                Text("Automatic is still checking. Tap Choose facing direction to select the mark the person is looking towards.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .accessibilityIdentifier("placement.waiting")
            }
            if camera.step == .processing {
                HStack { ProgressView().tint(signal); Text(camera.message) }
                    .accessibilityAddTraits(.updatesFrequently)
            } else {
                Button { heightFocused = false; primaryAction() } label: {
                    Text(primaryLabel).fontWeight(.semibold).frame(maxWidth: .infinity).padding(.vertical, 10)
                }
                .buttonStyle(.borderedProminent).tint(signal).foregroundStyle(.black)
                .disabled(!canContinue)
                .accessibilityIdentifier("flow.continue")
            }
        }.padding(.horizontal, 20).padding(.vertical, 12)
            .background(Color(red: 0.07, green: 0.08, blue: 0.10))
    }

    private var primaryLabel: String {
        switch camera.step {
        case .recognise: camera.running ? "Recognising…" : "Start recording"
        case .position: camera.recommendation.map { "Continue · camera mark \($0.marker.number)" } ?? "Choose facing direction"
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
        case .position:
            if camera.recommendation == nil { choosingFacing = true }
            else { camera.lockPlacement() }
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
    let facing: FloorMarker?
    var onSelect: ((FloorMarker) -> Void)?
    var body: some View {
        GeometryReader { geometry in
            let centre = CGPoint(x: geometry.size.width / 2, y: geometry.size.height / 2)
            let radius = min(geometry.size.width * 0.36, geometry.size.height * 0.39)
            VStack(spacing: 4) {
                if let facing {
                    Image(systemName: "arrow.up").font(.title2.bold()).foregroundStyle(.cyan)
                        .rotationEffect(.degrees(facing.angleDegrees))
                }
                Text("PERSON").font(.caption.bold())
            }.position(centre)
            ForEach(FloorMarker.allCases) { mark in
                Button { onSelect?(mark) } label: {
                    Text("\(mark.number)").font(.subheadline.bold())
                        .foregroundStyle(selected == mark ? .black : .white)
                        .frame(width: 44, height: 44)
                        .background(selected == mark ? Color(red: 0.79, green: 0.98, blue: 0.10) : Color.gray.opacity(0.25), in: Circle())
                        .overlay { if setup == mark { Circle().stroke(.white, lineWidth: 2) } }
                        .overlay { if facing == mark { Circle().stroke(.cyan, lineWidth: 3).padding(-4) } }
                }
                .buttonStyle(.plain)
                .allowsHitTesting(onSelect != nil)
                .position(x: centre.x + radius * mark.horizontal, y: centre.y + radius * mark.vertical)
                .accessibilityLabel("\(onSelect == nil ? "Mark" : "Face mark") \(mark.number), \(mark.title)\(selected == mark ? ", camera target" : "")\(setup == mark ? ", starting phone position" : "")")
                .accessibilityIdentifier("placement.mark.\(mark.number)")
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
