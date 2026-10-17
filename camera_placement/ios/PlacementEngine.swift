import Foundation

enum PlacementExercise: String, CaseIterable, Identifiable {
    case squat
    case pushup
    case lateralRaise = "lateral_raise"

    var id: String { rawValue }
    var title: String {
        switch self {
        case .squat: "Squat"
        case .pushup: "Push-up"
        case .lateralRaise: "Lateral raise"
        }
    }
    var view: String { self == .lateralRaise ? "Front" : "Side" }
    var heightFraction: Double {
        switch self {
        case .squat: 0.50
        case .pushup: 0.25
        case .lateralRaise: 0.65
        }
    }
}

enum FloorMarker: Int, CaseIterable, Identifiable {
    case top, topRight, right, bottomRight, bottom, bottomLeft, left, topLeft

    var id: Int { rawValue }
    var number: Int { rawValue + 1 }
    var angleDegrees: Double { Double(rawValue) * 45 }
    var title: String {
        switch self {
        case .top: "Top"
        case .topRight: "Top right"
        case .right: "Right"
        case .bottomRight: "Bottom right"
        case .bottom: "Bottom"
        case .bottomLeft: "Bottom left"
        case .left: "Left"
        case .topLeft: "Top left"
        }
    }
    var horizontal: Double { sin(angleDegrees * .pi / 180) }
    var vertical: Double { -cos(angleDegrees * .pi / 180) }
}

struct PlacementRecommendation: Equatable {
    let marker: FloorMarker
    let cameraHeightCM: Int
    let exercise: PlacementExercise
    let subjectHeadingDegrees: Double

    var summary: String { "Marker \(marker.number) · \(marker.title)" }

    // Clockwise around the floor map from the person's facing direction:
    // 0° is in front and 180° is behind. The pose is only an estimate, so
    // report the result in ten-degree steps rather than implying precision.
    var approximateCameraAngleDegrees: Int {
        let angle = (marker.angleDegrees - subjectHeadingDegrees + 360)
            .truncatingRemainder(dividingBy: 360)
        return Int((angle / 10).rounded()) * 10 % 360
    }
}

enum PlacementEngine {
    private static func distance(_ a: Double, _ b: Double) -> Double {
        abs((a - b + 540).truncatingRemainder(dividingBy: 360) - 180)
    }

    static func recommend(
        exercise: PlacementExercise,
        subjectHeightCM: Double,
        headingDegrees: Double,
        setupMarker: FloorMarker
    ) -> PlacementRecommendation? {
        guard subjectHeightCM.isFinite, (80...250).contains(subjectHeightCM), headingDegrees.isFinite else { return nil }
        let heading = (headingDegrees.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360)
        let ideals = exercise == .lateralRaise ? [heading] : [heading + 90, heading - 90]
        let marker = FloorMarker.allCases.min { a, b in
            let aView = ideals.map { distance(a.angleDegrees, $0) }.min()!
            let bView = ideals.map { distance(b.angleDegrees, $0) }.min()!
            if abs(aView - bView) > 0.0001 { return aView < bView }
            let aTravel = distance(a.angleDegrees, setupMarker.angleDegrees)
            let bTravel = distance(b.angleDegrees, setupMarker.angleDegrees)
            if abs(aTravel - bTravel) > 0.0001 { return aTravel < bTravel }
            return a.rawValue < b.rawValue
        }!
        return PlacementRecommendation(
            marker: marker,
            cameraHeightCM: Int((subjectHeightCM * exercise.heightFraction).rounded()),
            exercise: exercise,
            subjectHeadingDegrees: heading
        )
    }
}

struct FloorVector {
    let xRight: Double
    let zAway: Double
}

struct PoseDirectionEstimate {
    let degrees: Double
    let source: String
}

struct PoseImagePoint {
    let x: Double
    let y: Double
    let confidence: Double

    var usable: Bool {
        x.isFinite && y.isFinite && confidence.isFinite && confidence >= 0.6
            && (0.02...0.98).contains(x) && (0.02...0.98).contains(y)
    }
}

enum TorsoOrientation {
    // Use the torso plane, rather than assuming the shoulders are level.
    static func vector(leftShoulder: SIMD3<Double>, rightShoulder: SIMD3<Double>,
                       leftHip: SIMD3<Double>, rightHip: SIMD3<Double>) -> FloorVector? {
        func unit(_ value: SIMD3<Double>) -> SIMD3<Double>? {
            let length = sqrt(value.x * value.x + value.y * value.y + value.z * value.z)
            guard length.isFinite, length > 0.08 else { return nil }
            return value / length
        }
        guard let shoulders = unit(leftShoulder - rightShoulder),
              let hips = unit(leftHip - rightHip),
              shoulders.x * hips.x + shoulders.y * hips.y + shoulders.z * hips.z > 0.5,
              let left = unit(shoulders + hips),
              let up = unit((leftShoulder + rightShoulder - leftHip - rightHip) / 2) else { return nil }
        let front = SIMD3(left.y * up.z - left.z * up.y,
                          left.z * up.x - left.x * up.z,
                          left.x * up.y - left.y * up.x)
        guard hypot(front.x, front.z) > 0.3 else { return nil }
        return FloorVector(xRight: front.x, zAway: -front.z)
    }

    struct Profile {
        // nil means the torso is side-on but the face does not resolve left/right.
        let xDirection: Double?
    }

    // An independent 2D check: a reconstructed 3D shoulder depth alone is not
    // reliable evidence that a visibly side-on person faces the setup camera.
    // Thresholds are provisional and require physical-device validation.
    static func standingProfile(leftShoulder: PoseImagePoint, rightShoulder: PoseImagePoint,
                                leftHip: PoseImagePoint, rightHip: PoseImagePoint,
                                nose: PoseImagePoint?, ears: [PoseImagePoint],
                                imageAspect: Double) -> Profile? {
        guard imageAspect.isFinite, imageAspect > 0,
              [leftShoulder, rightShoulder, leftHip, rightHip].allSatisfy(\.usable) else { return nil }
        let shoulderX = (leftShoulder.x + rightShoulder.x) / 2 * imageAspect
        let shoulderY = (leftShoulder.y + rightShoulder.y) / 2
        let hipX = (leftHip.x + rightHip.x) / 2 * imageAspect
        let hipY = (leftHip.y + rightHip.y) / 2
        let torso = hypot(shoulderX - hipX, shoulderY - hipY)
        guard torso > 0.08, shoulderY - hipY > 0.7 * torso,
              abs(leftShoulder.x - rightShoulder.x) * imageAspect < 0.35 * torso,
              abs(leftHip.x - rightHip.x) * imageAspect < 0.30 * torso else { return nil }
        guard let nose, nose.usable,
              nose.y > shoulderY, nose.y - shoulderY < torso,
              abs(nose.x * imageAspect - shoulderX) < torso * 0.6 else {
            return Profile(xDirection: nil)
        }
        let visibleEars = ears.filter { $0.usable && abs($0.y - nose.y) < torso * 0.25 }
        let offsets = visibleEars.map { (nose.x - $0.x) * imageAspect }
        let ahead = nose.x * imageAspect - shoulderX
        if !offsets.isEmpty, ahead > torso * 0.06, offsets.allSatisfy({ $0 > torso * 0.06 }) {
            return Profile(xDirection: 1)
        }
        if !offsets.isEmpty, ahead < -torso * 0.06, offsets.allSatisfy({ $0 < -torso * 0.06 }) {
            return Profile(xDirection: -1)
        }
        return Profile(xDirection: nil)
    }
}

enum PoseHeading {
    // The rear setup camera points from its known marker toward the subject.
    static func floorHeading(from vector: FloorVector, setupMarker: FloorMarker) -> Double? {
        guard vector.xRight.isFinite, vector.zAway.isFinite,
              hypot(vector.xRight, vector.zAway) > 0.15 else { return nil }
        let local = atan2(vector.xRight, vector.zAway) * 180 / .pi
        let cameraLooks = setupMarker.angleDegrees + 180
        return (cameraLooks + local + 720).truncatingRemainder(dividingBy: 360)
    }
}

struct HeadingWindow {
    private(set) var values: [Double] = []

    mutating func reset() { values.removeAll() }

    mutating func add(_ angle: Double) -> Double? {
        values.append(angle)
        if values.count > 5 { values.removeFirst() }
        guard values.count >= 3 else { return nil }
        let radians = values.map { $0 * .pi / 180 }
        let x = radians.reduce(0) { $0 + sin($1) }
        let y = radians.reduce(0) { $0 + cos($1) }
        let mean = (atan2(x, y) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
        let spread = values.map { abs(($0 - mean + 540).truncatingRemainder(dividingBy: 360) - 180) }.max()!
        return spread <= 25 ? mean : nil
    }
}

/// Only stable samples refresh a recommendation. Raw but conflicting samples
/// must not keep an old marker alive indefinitely.
struct HeadingTracker {
    private var window = HeadingWindow()
    private var lastSample: Double?
    private var lastStable: Double?
    private var stable: Double?

    mutating func reset() { self = HeadingTracker() }

    func current(at time: Double) -> Double? {
        guard let lastStable, time - lastStable < 2 else { return nil }
        return stable
    }

    mutating func add(_ heading: Double?, at time: Double) -> Double? {
        if let lastSample, time - lastSample > 1.3 { window.reset() }
        if let heading, heading.isFinite {
            lastSample = time
            if let value = window.add(heading) {
                stable = value
                lastStable = time
            }
        }
        return current(at: time)
    }
}
