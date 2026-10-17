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
