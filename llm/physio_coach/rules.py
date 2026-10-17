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
    if len(request.snapshots) == 1:
        return evaluate_capture(request)
    if not _suitable_view(request):
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


GENERAL_TIPS = {
    "squat": Candidate(
        "squat_general", "Keep your weight through your heels and your knees in line with your toes.",
        "General squat form tip.",
    ),
    "pushup": Candidate(
        "pushup_general", "Keep your body in one straight line from head to heels.",
        "General push-up form tip.",
    ),
    "lateral_raise": Candidate(
        "raise_general", "Lift with a slight bend in your elbows and lower slowly.",
        "General lateral-raise form tip.",
    ),
}


def _suitable_view(request: FeedbackRequest) -> bool:
    angle = abs(request.camera_angle_deg)
    return abs(angle - 90) <= 30 if request.exercise in {"squat", "pushup"} else angle <= 30


def evaluate_capture(request: FeedbackRequest) -> Evaluation:
    """Always offer feedback for one image, using whatever measurements exist.

    One photo cannot show the movement peak, so depth and range cues are
    conditional ("if this is the lowest point..."). Corrections come first,
    then positive confirmations, then a general tip that is always eligible.
    """
    capture = request.snapshots[0]
    general = GENERAL_TIPS[request.exercise]
    if not _suitable_view(request):
        return Evaluation(True, "The camera angle limits what this photo can measure, so this is a general tip.", (general,))
    if not _has_usable_peak(request.exercise, capture):
        return Evaluation(True, "The photo did not show enough clear body points to measure, so this is a general tip.", (general,))

    corrections: list[Candidate] = []
    positives: list[Candidate] = []
    if request.exercise == "squat":
        knees = _available(capture.knee_left_deg, capture.knee_right_deg)
        if knees:
            knee = min(knees)
            if knee > 100:
                corrections.append(Candidate("capture_squat_depth", "If this is the lowest point of your squat, try sitting a little deeper.", f"In this photo the most-bent knee is about {knee:.0f}° (target at the bottom: 100° or less)."))
            else:
                positives.append(Candidate("capture_squat_depth_good", "Good depth here, your knees are well bent.", f"In this photo the most-bent knee is about {knee:.0f}°, within the 100° depth target."))
        torso = capture.torso_inclination_deg
        if torso is not None and torso <= 90:
            if torso > 45:
                corrections.append(Candidate("capture_squat_torso", "Try keeping your chest a little more upright.", f"In this photo the torso leans about {torso:.0f}° from vertical (target: 45° or less)."))
            else:
                positives.append(Candidate("capture_squat_torso_good", "Nice upright chest.", f"In this photo the torso leans about {torso:.0f}° from vertical, within the 45° target."))
    elif request.exercise == "pushup":
        elbows = _available(capture.elbow_left_deg, capture.elbow_right_deg)
        if elbows:
            elbow = min(elbows)
            if elbow > 90:
                corrections.append(Candidate("capture_pushup_depth", "If this is your lowest point, try lowering your chest a little further.", f"In this photo the most-bent elbow is about {elbow:.0f}° (target at the bottom: 90° or less)."))
            else:
                positives.append(Candidate("capture_pushup_depth_good", "Good depth, your elbows are well bent.", f"In this photo the most-bent elbow is about {elbow:.0f}°, within the 90° depth target."))
        paired = [
            (alignment, offset)
            for alignment, offset in (
                (capture.body_alignment_left_deg, capture.hip_offset_left_torso_lengths),
                (capture.body_alignment_right_deg, capture.hip_offset_right_torso_lengths),
            )
            if alignment is not None and offset is not None
        ]
        alignments = _available(capture.body_alignment_left_deg, capture.body_alignment_right_deg)
        if paired and all(alignment < 165 and offset < -0.1 for alignment, offset in paired):
            corrections.append(Candidate("capture_pushup_hips_low", "Lift your hips a little to keep your body straight.", "In this photo the hips sit below the shoulder-to-ankle line."))
        elif paired and all(alignment < 165 and offset > 0.1 for alignment, offset in paired):
            corrections.append(Candidate("capture_pushup_hips_high", "Lower your hips a little to keep your body straight.", "In this photo the hips sit above the shoulder-to-ankle line."))
        elif alignments and all(value >= 165 for value in alignments):
            positives.append(Candidate("capture_pushup_line_good", "Your body is in a nice straight line.", f"In this photo body alignment is about {min(alignments):.0f}° (target: 165° to 180°)."))
    else:
        arms = _available(capture.arm_left_deg, capture.arm_right_deg)
        if arms:
            if all(value < 80 for value in arms):
                corrections.append(Candidate("capture_raise_low", "If this is the top of the lift, raise your arms up to shoulder height.", f"In this photo the arms are at about {max(arms):.0f}° (target at the top: 80° to 100°)."))
            elif all(value > 100 for value in arms):
                corrections.append(Candidate("capture_raise_high", "Stop at shoulder height rather than lifting higher.", f"In this photo the arms are at about {min(arms):.0f}° (target at the top: 80° to 100°)."))
            elif all(80 <= value <= 100 for value in arms):
                positives.append(Candidate("capture_raise_height_good", "Good height, your arms are at about shoulder level.", "In this photo the arms are within the 80° to 100° shoulder-height range."))
        difference = capture.arm_difference_deg
        if difference is not None:
            if difference > 10:
                corrections.append(Candidate("capture_uneven_arms", "Try lifting both arms evenly.", f"In this photo the arms differ by about {difference:.0f}° (target: 10° or less)."))
            else:
                positives.append(Candidate("capture_even_arms", "Nice and even on both sides.", f"In this photo the arms are within {difference:.0f}° of each other."))
    return Evaluation(
        True,
        "This photo shows one moment, so depth and range cues assume it is the key position of the movement.",
        tuple(corrections + positives + [general]),
    )
