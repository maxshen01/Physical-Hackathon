import pytest
from pydantic import ValidationError

from llm.physio_coach.models import FeedbackRequest
from llm.physio_coach.rules import evaluate


def request(exercise, peak, angle=90, start=None, finish=None):
    return FeedbackRequest.model_validate({
        "exercise": exercise,
        "camera_angle_deg": angle,
        "snapshots": [
            {"phase": "start", **(start or {})},
            {"phase": "peak", **peak},
            {"phase": "finish", **(finish or {})},
        ],
    })


def cue_ids(value):
    return {cue.id for cue in evaluate(value).candidates}


def test_squat_uses_peak_and_available_sides():
    value = request("squat", {"knee_left_deg": 112, "torso_inclination_deg": 50},
                    start={"knee_left_deg": 70}, finish={"torso_inclination_deg": 10})
    assert cue_ids(value) == {"squat_depth", "squat_torso"}
    assert not cue_ids(request("squat", {"knee_left_deg": 112, "knee_right_deg": 90}))


def test_pushup_elbows_and_both_hip_directions():
    assert cue_ids(request("pushup", {"elbow_left_deg": 100})) == {"pushup_depth"}
    assert cue_ids(request("pushup", {"body_alignment_left_deg": 155, "hip_offset_left_torso_lengths": -0.2})) == {"pushup_hips_low"}
    assert cue_ids(request("pushup", {"body_alignment_left_deg": 155, "hip_offset_left_torso_lengths": 0.2})) == {"pushup_hips_high"}
    assert not cue_ids(request("pushup", {"body_alignment_left_deg": 155, "hip_offset_left_torso_lengths": 0.08}))
    assert not cue_ids(request("pushup", {"body_alignment_left_deg": 170, "hip_offset_left_torso_lengths": 0.2}))


def test_lateral_raise_targets_and_symmetry():
    assert cue_ids(request("lateral_raise", {"arm_left_deg": 70, "arm_right_deg": 72, "arm_difference_deg": 2}, angle=0)) == {"raise_low"}
    assert cue_ids(request("lateral_raise", {"arm_left_deg": 110, "arm_right_deg": 112, "arm_difference_deg": 2}, angle=0)) == {"raise_high"}
    assert cue_ids(request("lateral_raise", {"arm_left_deg": 70, "arm_right_deg": 90, "arm_difference_deg": 20}, angle=0)) == {"raise_uneven"}


def test_view_and_missing_peak_are_unassessable():
    assert not evaluate(request("squat", {"knee_left_deg": 120}, angle=59)).assessable
    assert evaluate(request("squat", {"knee_left_deg": 120}, angle=-120)).assessable
    assert not evaluate(request("lateral_raise", {"arm_left_deg": 70}, angle=31)).assessable
    assert not evaluate(request("squat", {}, start={"knee_left_deg": 120})).assessable
    assert not evaluate(request("pushup", {"body_alignment_left_deg": 150})).assessable


@pytest.mark.parametrize("change", [
    {"camera_angle_deg": 181},
    {"exercise": "unknown"},
    {"snapshots": [{"phase": "start"}, {"phase": "finish"}, {"phase": "peak"}]},
    {"snapshots": [{"phase": "peak"}]},
])
def test_invalid_request_shape(change):
    base = request("squat", {"knee_left_deg": 120}).model_dump()
    base.update(change)
    with pytest.raises(ValidationError):
        FeedbackRequest.model_validate(base)


def test_invalid_angles_and_arm_difference():
    with pytest.raises(ValidationError):
        request("squat", {"knee_left_deg": 181})
    with pytest.raises(ValidationError):
        request("lateral_raise", {"arm_left_deg": 80, "arm_right_deg": 100, "arm_difference_deg": 5}, angle=0)
    with pytest.raises(ValidationError):
        request("pushup", {"hip_offset_left_torso_lengths": float("inf")})
    with pytest.raises(ValidationError):
        request("squat", {"arm_left_deg": 90})


def capture(exercise, values, angle=None):
    angle = (0 if exercise == "lateral_raise" else 90) if angle is None else angle
    return FeedbackRequest.model_validate({
        "exercise": exercise, "camera_angle_deg": angle,
        "snapshots": [{"phase": "capture", **values}],
    })


def capture_ids(value):
    return [cue.id for cue in evaluate(value).candidates]


def test_capture_always_offers_feedback_even_without_measurements():
    for exercise in ("squat", "pushup", "lateral_raise"):
        result = evaluate(capture(exercise, {}))
        assert result.assessable and [cue.id for cue in result.candidates][-1].endswith("_general")
        wrong_view = evaluate(capture(exercise, {}, angle=45 if exercise == "lateral_raise" else 0))
        assert wrong_view.assessable and len(wrong_view.candidates) == 1


def test_capture_orders_corrections_before_positives_and_general_tip():
    ids = capture_ids(capture("squat", {"knee_left_deg": 140, "torso_inclination_deg": 20}))
    assert ids == ["capture_squat_depth", "capture_squat_torso_good", "squat_general"]
    assert capture_ids(capture("squat", {"knee_left_deg": 90}))[0] == "capture_squat_depth_good"
    assert capture_ids(capture("squat", {"torso_inclination_deg": 175})) == ["squat_general"]
    assert capture_ids(capture("pushup", {"elbow_right_deg": 106, "body_alignment_right_deg": 172, "hip_offset_right_torso_lengths": -0.1})) == [
        "capture_pushup_depth", "capture_pushup_line_good", "pushup_general"]
    assert capture_ids(capture("lateral_raise", {"arm_left_deg": 94, "arm_right_deg": 92, "arm_difference_deg": 2})) == [
        "capture_raise_height_good", "capture_even_arms", "raise_general"]
    assert capture_ids(capture("lateral_raise", {"arm_left_deg": 95, "arm_right_deg": 78, "arm_difference_deg": 17}))[0] == "capture_uneven_arms"


def test_capture_depth_cues_stay_conditional():
    cues = {cue.id: cue.cue for cue in evaluate(capture("squat", {"knee_left_deg": 140})).candidates}
    assert cues["capture_squat_depth"].startswith("If this is the lowest point")
