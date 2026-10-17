import Foundation

@main
struct PlacementFlowTests {
    @MainActor
    static func waitFor(_ description: String, _ condition: () -> Bool) async {
        for _ in 0..<100 {
            if condition() { return }
            try? await Task.sleep(nanoseconds: 20_000_000)
        }
        preconditionFailure("Timed out: \(description)")
    }

    @MainActor
    static func main() async {
        let camera = CameraModel.placementTestModel()
        precondition(camera.step == .position && camera.recommendation == nil)
        camera.configurePlacement(heightCM: 170, setupMarker: .bottom, facingOverride: .left)
        await waitFor("manual facing resolves a blocked automatic scan") { camera.recommendation?.marker == .bottom }
        precondition(camera.recommendation?.cameraHeightCM == 85)
        camera.lockPlacement()
        await waitFor("Continue advances to capture") { camera.step == .capture }
        camera.revisePlacement()
        await waitFor("position can be changed without reclassifying") {
            camera.step == .position && camera.recommendation?.marker == .bottom
        }
        precondition(camera.labelLocked && camera.exercise == "Squat")
        camera.configurePlacement(heightCM: 0, setupMarker: .bottom, facingOverride: .left)
        await waitFor("invalid height clears the position and explains why") {
            camera.recommendation == nil && camera.message.contains("80 and 250")
        }
        camera.lockPlacement()
        await waitFor("invalid height cannot advance") { camera.message.contains("before continuing") }
        precondition(camera.step == .position)
        camera.configurePlacement(heightCM: 180, setupMarker: .bottom, facingOverride: .right)
        await waitFor("correcting the height restores progression") { camera.recommendation?.cameraHeightCM == 90 }
        camera.lockPlacement()
        await waitFor("a second valid selection advances") { camera.step == .capture }

        let expired = CameraModel.placementTestModel(expiredAutomatic: true)
        expired.lockPlacement()
        await waitFor("expired automatic estimate provides an actionable error") {
            expired.recommendation == nil && expired.message.contains("expired")
        }
        precondition(expired.step == .position)
        expired.configurePlacement(heightCM: 170, setupMarker: .bottom, facingOverride: .left)
        await waitFor("manual choice recovers from an expired estimate") { expired.recommendation?.marker == .bottom }
        expired.lockPlacement()
        await waitFor("recovered placement advances") { expired.step == .capture }
        print("Placement flow checks passed: blocked automatic scan, manual selection, capture, back, height validation, expired estimate recovery")
    }
}
