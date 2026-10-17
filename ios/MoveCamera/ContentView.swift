import AVFoundation
import SwiftUI

struct ContentView: View {
    private let signal = Color(red: 0.79, green: 0.98, blue: 0.10)
    private let panel = Color(red: 0.12, green: 0.14, blue: 0.17)
    @StateObject private var camera = PlacementCameraModel()
    @State private var exercise: PlacementExercise = .squat
    @State private var heightText = "170"
    @State private var setupMarker: FloorMarker = .bottom
    @Environment(\.scenePhase) private var scenePhase

    private var heightCM: Double { Double(heightText) ?? 0 }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Image("OrbitLogo")
                    .resizable().scaledToFit().frame(width: 160, height: 60, alignment: .leading)
                    .accessibilityLabel("Orbit")
                Text("CAMERA PLACEMENT").font(.caption.bold()).tracking(2).foregroundStyle(signal)

                PlacementCameraPreview(session: camera.session)
                    .overlay(alignment: .topLeading) {
                        if camera.running {
                            Text(camera.locked ? "PLACEMENT LOCKED" : "LIVE SETUP")
                                .font(.caption.bold()).padding(9)
                                .foregroundStyle(.black)
                                .background(signal, in: Capsule()).padding()
                        }
                    }
                    .overlay {
                        if !camera.running {
                            VStack(spacing: 10) {
                                Image(systemName: "camera.viewfinder").font(.largeTitle)
                                Text("Stand at your chosen setup mark.\nKeep the person fully in view.")
                                    .multilineTextAlignment(.center)
                            }.foregroundStyle(.white)
                        }
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .frame(height: 275)

                VStack(alignment: .leading, spacing: 12) {
                    Picker("Exercise", selection: $exercise) {
                        ForEach(PlacementExercise.allCases) { item in Text(item.title).tag(item) }
                    }
                    HStack {
                        Text("Subject height")
                        Spacer()
                        TextField("170", text: $heightText)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 75)
                            .textFieldStyle(.roundedBorder)
                        Text("cm")
                    }
                    Picker("Setup camera mark", selection: $setupMarker) {
                        ForEach(FloorMarker.allCases) { mark in
                            Text("\(mark.number) · \(mark.title)").tag(mark)
                        }
                    }
                }
                .padding(14)
                .background(panel, in: RoundedRectangle(cornerRadius: 16))

                VStack(alignment: .leading, spacing: 10) {
                    if let result = camera.recommendation {
                        Text(result.summary).font(.title2.bold())
                        Text("Place the phone at mark \(result.marker.number). Set the camera lens \(result.cameraHeightCM) cm above the floor.")
                        Text("Approx. camera angle: \(result.approximateCameraAngleDegrees)° clockwise from the subject’s facing direction")
                            .font(.subheadline)
                        Text("\(result.exercise.view) view · \(Int(result.exercise.heightFraction * 100))% of subject height")
                            .font(.caption).foregroundStyle(.secondary)
                    } else {
                        Text("Waiting for a clear direction").font(.title3.bold())
                        Text("A position appears after the phone sees a steady, full-body pose from the setup mark.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    FloorMap(selected: camera.recommendation?.marker, setup: setupMarker)
                        .frame(height: 175)
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(panel, in: RoundedRectangle(cornerRadius: 16))

                HStack(spacing: 10) {
                    Button(camera.running ? "Stop" : "Start setup camera") {
                        if camera.running { camera.stop() }
                        else { camera.start(exercise: exercise, heightCM: heightCM, setupMarker: setupMarker) }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(signal)
                    .frame(maxWidth: .infinity)
                    if camera.running {
                        Button(camera.locked ? "Scan again" : "Lock placement") {
                            if camera.locked { camera.scanAgain() }
                            else { camera.lockPlacement() }
                        }
                        .buttonStyle(.bordered)
                        .disabled(!camera.locked && camera.recommendation == nil)
                    }
                }
                if camera.locked {
                    Button("Take photo") { camera.capturePhoto() }
                        .buttonStyle(.borderedProminent)
                        .tint(signal)
                        .frame(maxWidth: .infinity)
                }
                Text(camera.message).font(.footnote).foregroundStyle(.secondary)
                    .accessibilityAddTraits(.updatesFrequently)
                Text("Camera placement only. If an exercise causes pain or conflicts with your prescribed plan, stop and consult your physiotherapist.")
                    .font(.caption2).foregroundStyle(.secondary)
            }
            .padding(20)
        }
        .background(Color(red: 0.07, green: 0.08, blue: 0.10))
        .preferredColorScheme(.dark)
        .onChange(of: exercise) { _, value in camera.update(exercise: value, heightCM: heightCM, setupMarker: setupMarker) }
        .onChange(of: heightText) { _, _ in camera.update(exercise: exercise, heightCM: heightCM, setupMarker: setupMarker) }
        .onChange(of: setupMarker) { _, value in camera.update(exercise: exercise, heightCM: heightCM, setupMarker: value) }
        .onChange(of: scenePhase) { _, phase in if phase != .active { camera.stop() } }
        .sheet(isPresented: Binding(
            get: { camera.capturedPhoto != nil },
            set: { if !$0 { camera.clearPhoto() } }
        )) {
            NavigationStack {
                Group {
                    if let photo = camera.capturedPhoto {
                        Image(uiImage: photo).resizable().scaledToFit()
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .background(.black)
                    }
                }
                .navigationTitle("Captured photo")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { camera.clearPhoto() }
                } }
            }
        }
    }
}

private struct FloorMap: View {
    let selected: FloorMarker?
    let setup: FloorMarker

    var body: some View {
        GeometryReader { geometry in
            let centre = CGPoint(x: geometry.size.width / 2, y: geometry.size.height / 2)
            let radius = min(geometry.size.width * 0.36, geometry.size.height * 0.39)
            Text("SUBJECT")
                .font(.caption.bold())
                .position(centre)
            ForEach(FloorMarker.allCases) { mark in
                Text("\(mark.number)")
                    .font(.caption.bold())
                    .foregroundStyle(selected == mark ? .black : .white)
                    .frame(width: 30, height: 30)
                    .background(selected == mark ? Color(red: 0.79, green: 0.98, blue: 0.10) : Color.gray.opacity(0.25), in: Circle())
                    .overlay { if setup == mark { Circle().stroke(.cyan, lineWidth: 2) } }
                    .position(x: centre.x + radius * mark.horizontal, y: centre.y + radius * mark.vertical)
                    .accessibilityLabel("Mark \(mark.number), \(mark.title)\(selected == mark ? ", recommended" : "")\(setup == mark ? ", setup camera" : "")")
            }
        }
        .accessibilityElement(children: .contain)
    }
}

private struct PlacementCameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    func makeUIView(context: Context) -> PlacementPreviewView {
        let view = PlacementPreviewView()
        view.preview.session = session
        view.preview.videoGravity = .resizeAspect
        return view
    }
    func updateUIView(_ uiView: PlacementPreviewView, context: Context) {}
}

private final class PlacementPreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    override init(frame: CGRect) { super.init(frame: frame); backgroundColor = .black }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() {
        super.layoutSubviews()
        if let connection = preview.connection, connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }
    }
}
