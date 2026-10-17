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
