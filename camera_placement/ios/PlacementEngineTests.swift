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
        print("Placement engine checks passed")
    }
}
