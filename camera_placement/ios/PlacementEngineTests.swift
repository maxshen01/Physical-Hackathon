import Foundation

@main
struct PlacementEngineTests {
    static func main() {
        let markers = FloorMarker.allCases
        for (index, marker) in markers.enumerated() {
            let result = PlacementEngine.recommend(
                exercise: .lateralRaise, subjectHeightCM: 160,
                headingDegrees: Double(index * 45), setupMarker: .bottom
            )!
            precondition(result.marker == marker, "front view should select mark \(index + 1)")
            precondition(result.cameraHeightCM == 104)
        }
        let squat = PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 170, headingDegrees: 0, setupMarker: .bottom)!
        precondition(squat.marker == .right && squat.cameraHeightCM == 85)
        let facesLeft = PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 170, headingDegrees: 270, setupMarker: .bottom)!
        precondition(facesLeft.marker == .bottom && facesLeft.cameraHeightCM == 85)
        let left = PlacementEngine.recommend(exercise: .pushup, subjectHeightCM: 180, headingDegrees: 0, setupMarker: .left)!
        precondition(left.marker == .left && left.cameraHeightCM == 45)
        let facesDown = PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 170, headingDegrees: 180, setupMarker: .left)!
        precondition(facesDown.marker == .left && facesDown.approximateCameraAngleDegrees == 90)
        let turnsSlightlyRight = PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 170, headingDegrees: 160, setupMarker: .left)!
        precondition(turnsSlightlyRight.marker == .left && turnsSlightlyRight.approximateCameraAngleDegrees == 110)
        let wrapAround = PlacementRecommendation(marker: .top, cameraHeightCM: 85, exercise: .squat, subjectHeadingDegrees: 356)
        precondition(wrapAround.approximateCameraAngleDegrees == 0)
        precondition(PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 0, headingDegrees: 0, setupMarker: .bottom) == nil)

        let facesSetupCamera = FloorVector(xRight: 0, zAway: -1)
        precondition(PoseHeading.floorHeading(from: facesSetupCamera, setupMarker: .bottom) == 180)
        precondition(PoseHeading.floorHeading(from: facesSetupCamera, setupMarker: .right) == 90)
        precondition(PoseHeading.floorHeading(from: FloorVector(xRight: 0, zAway: 0), setupMarker: .bottom) == nil)

        var window = HeadingWindow()
        precondition(window.add(355) == nil)
        precondition(window.add(2) == nil)
        let circularMean = window.add(5)!
        precondition(circularMean < 10 || circularMean > 350)
        window.reset()
        precondition(window.add(0) == nil)
        precondition(window.add(90) == nil)
        precondition(window.add(180) == nil)

        // Model-independent floor conversion, including all setup positions,
        // back-facing subjects and a torso leaning forward during a squat.
        for setup in FloorMarker.allCases {
            for localDegrees in stride(from: 0.0, to: 360.0, by: 45.0) {
                let radians = localDegrees * .pi / 180
                let leftAxis = SIMD3(-cos(radians), 0, -sin(radians))
                let shoulderCentre = SIMD3(sin(radians) * 0.2, 0.5, -cos(radians) * 0.2)
                let vector = TorsoOrientation.vector(
                    leftShoulder: shoulderCentre + leftAxis * 0.2,
                    rightShoulder: shoulderCentre - leftAxis * 0.2,
                    leftHip: leftAxis * 0.15, rightHip: -leftAxis * 0.15
                )!
                let expected = (setup.angleDegrees + 180 + localDegrees).truncatingRemainder(dividingBy: 360)
                let actual = PoseHeading.floorHeading(from: vector, setupMarker: setup)!
                precondition(abs((actual - expected + 540).truncatingRemainder(dividingBy: 360) - 180) < 0.001)
            }
        }

        // A clear image profile must beat a frontal 3D reconstruction. Pixel
        // aspect ratio must not turn a broad torso into an apparent profile.
        for aspect in [9.0 / 16, 1, 16.0 / 9] {
            func point(_ xOffset: Double, _ y: Double, confidence: Double = 1) -> PoseImagePoint {
                PoseImagePoint(x: 0.5 + xOffset / aspect, y: y, confidence: confidence)
            }
            for direction in [-1.0, 1.0] {
                let profile = TorsoOrientation.standingProfile(
                    leftShoulder: point(-0.01, 0.6), rightShoulder: point(0.01, 0.6),
                    leftHip: point(-0.01, 0.35), rightHip: point(0.01, 0.35),
                    nose: point(direction * 0.06, 0.75), ears: [point(direction * 0.01, 0.75)],
                    imageAspect: aspect
                )!
                precondition(profile.xDirection == direction)
                let heading = PoseHeading.floorHeading(from: FloorVector(xRight: profile.xDirection!, zAway: 0), setupMarker: .bottom)!
                let result = PlacementEngine.recommend(exercise: .squat, subjectHeightCM: 170, headingDegrees: heading, setupMarker: .bottom)!
                precondition(result.marker == .bottom, "A side-on squat is photographed from the setup mark")
            }
            let turnedHeadOnly = TorsoOrientation.standingProfile(
                leftShoulder: point(-0.13, 0.6), rightShoulder: point(0.13, 0.6),
                leftHip: point(-0.09, 0.35), rightHip: point(0.09, 0.35),
                nose: point(0.06, 0.75), ears: [point(0.01, 0.75)], imageAspect: aspect
            )
            precondition(turnedHeadOnly == nil, "Turning the head does not rotate a broad, frontal torso")
            let unresolvedProfile = TorsoOrientation.standingProfile(
                leftShoulder: point(-0.01, 0.6), rightShoulder: point(0.01, 0.6),
                leftHip: point(-0.01, 0.35), rightHip: point(0.01, 0.35),
                nose: nil, ears: [], imageAspect: aspect
            )
            precondition(unresolvedProfile != nil && unresolvedProfile?.xDirection == nil)
        }

        var tracker = HeadingTracker()
        precondition(tracker.add(180, at: 0) == nil)
        precondition(tracker.add(180, at: 0.45) == nil)
        precondition(tracker.add(180, at: 0.9) == 180)
        _ = tracker.add(0, at: 1.35)
        _ = tracker.add(90, at: 1.8)
        _ = tracker.add(180, at: 2.25)
        _ = tracker.add(270, at: 2.7)
        precondition(tracker.add(0, at: 3.15) == nil, "Unstable raw readings must not keep the old facing alive")
        precondition(tracker.current(at: 3.15) == nil, "An expired estimate cannot be locked")
        tracker.reset()
        _ = tracker.add(0, at: 0); _ = tracker.add(0, at: 0.45); _ = tracker.add(0, at: 0.9)
        precondition(tracker.add(nil, at: 3) == nil)
        precondition(tracker.add(90, at: 3.1) == nil)
        precondition(tracker.add(90, at: 3.55) == nil)
        precondition(abs(tracker.add(90, at: 4)! - 90) < 0.001)
        print("Placement engine checks passed")
    }
}
