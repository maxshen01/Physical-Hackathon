"""Conservative, measurement-backed cues for the three supported exercises."""

from dataclasses import dataclass

from .models import FeedbackRequest, Snapshot


@dataclass(frozen=True)
class Candidate:
    id: str
    cue: str
    observation: str


@dataclass(frozen=True)
class Evaluation:
    assessable: bool
    reason: str
    candidates: tuple[Candidate, ...] = ()


def _available(*values: float | None) -> list[float]:
    return [value for value in values if value is not None]


def _matching(values: list[float], predicate) -> bool:
    return bool(values) and all(predicate(value) for value in values)


def _has_usable_peak(exercise: str, peak: Snapshot) -> bool:
    if exercise == "squat":
        return bool(_available(peak.knee_left_deg, peak.knee_right_deg, peak.torso_inclination_deg))
    if exercise == "pushup":
        return bool(_available(peak.elbow_left_deg, peak.elbow_right_deg)) or any(
            alignment is not None and offset is not None
            for alignment, offset in (
                (peak.body_alignment_left_deg, peak.hip_offset_left_torso_lengths),
                (peak.body_alignment_right_deg, peak.hip_offset_right_torso_lengths),
            )
        )
    return bool(_available(peak.arm_left_deg, peak.arm_right_deg, peak.arm_difference_deg))


def evaluate(request: FeedbackRequest) -> Evaluation:
    """Only peak values trigger cues; start/finish remain LLM context."""
    angle = abs(request.camera_angle_deg)
    suitable_view = (
        abs(angle - 90) <= 30 if request.exercise in {"squat", "pushup"}
        else angle <= 30
    )
    if not suitable_view:
        return Evaluation(False, "The camera angle does not support reliable cues for this exercise.")

    peak = request.snapshots[1]
    if not _has_usable_peak(request.exercise, peak):
        return Evaluation(False, "No usable measurements were supplied for the peak stage.")

    candidates: list[Candidate] = []
    if request.exercise == "squat":
        knees = _available(peak.knee_left_deg, peak.knee_right_deg)
        if _matching(knees, lambda value: value > 100):
            candidates.append(Candidate("squat_depth", "Go deeper", "At the deepest squat, the measured knee angle stayed above 100° on each available side."))
        if peak.torso_inclination_deg is not None and peak.torso_inclination_deg > 45:
            candidates.append(Candidate("squat_torso", "Chest up", f"At the deepest squat, torso inclination was {peak.torso_inclination_deg:g}° (target: 45° or less)."))

    elif request.exercise == "pushup":
        elbows = _available(peak.elbow_left_deg, peak.elbow_right_deg)
        if _matching(elbows, lambda value: value > 90):
            candidates.append(Candidate("pushup_depth", "Lower your chest", "At the lowest push-up position, the measured elbow angle stayed above 90° on each available side."))
        paired = [
            (alignment, offset)
            for alignment, offset in (
                (peak.body_alignment_left_deg, peak.hip_offset_left_torso_lengths),
                (peak.body_alignment_right_deg, peak.hip_offset_right_torso_lengths),
            )
            if alignment is not None and offset is not None
        ]
        if paired and all(alignment < 165 and offset < -0.1 for alignment, offset in paired):
            candidates.append(Candidate("pushup_hips_low", "Lift your hips", "At the lowest push-up position, body alignment was below 165° and the hips were more than 0.1 torso lengths below the shoulder–ankle line."))
        elif paired and all(alignment < 165 and offset > 0.1 for alignment, offset in paired):
            candidates.append(Candidate("pushup_hips_high", "Drop your hips", "At the lowest push-up position, body alignment was below 165° and the hips were more than 0.1 torso lengths above the shoulder–ankle line."))

    else:
        arms = _available(peak.arm_left_deg, peak.arm_right_deg)
        if _matching(arms, lambda value: value < 80):
            candidates.append(Candidate("raise_low", "Raise to shoulder height", "At the highest lateral-raise position, each available arm angle was below 80°."))
        elif _matching(arms, lambda value: value > 100):
            candidates.append(Candidate("raise_high", "Don't go above your shoulders", "At the highest lateral-raise position, each available arm angle was above 100°."))
        if peak.arm_difference_deg is not None and peak.arm_difference_deg > 10:
            candidates.append(Candidate("raise_uneven", "Raise both arms evenly", f"At the highest lateral-raise position, the arm-angle difference was {peak.arm_difference_deg:g}° (target: 10° or less)."))

    return Evaluation(True, "Peak-stage measurements were available for review.", tuple(candidates))
