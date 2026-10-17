"""Decode short uploads and extract timestamped JPEG frames."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess


MAX_DURATION_SECONDS = 30.0
FRAME_COUNT = 12


class VideoError(Exception):
    """The uploaded file cannot be analysed as a short video."""


class VideoToolsMissing(Exception):
    """FFmpeg or FFprobe is unavailable."""


@dataclass(frozen=True)
class Frame:
    timestamp_seconds: float
    path: Path


def _run(command: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VideoToolsMissing("FFmpeg and FFprobe must be installed on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoError("Video processing took too long") from exc


def _duration_from_packets(video_path: Path) -> float:
    """Some browser-created WebM files have no container duration metadata."""
    probe = _run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "packet=pts_time,duration_time",
            "-of", "json", str(video_path),
        ]
    )
    if probe.returncode:
        return 0.0
    try:
        packets = json.loads(probe.stdout).get("packets", [])
    except (TypeError, ValueError):
        return 0.0
    end = 0.0
    for packet in packets:
        try:
            pts = float(packet["pts_time"])
            length = float(packet.get("duration_time", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(pts) and math.isfinite(length):
            end = max(end, pts + max(0.0, length))
    return end


def extract_frames(video_path: Path, work_dir: Path) -> list[Frame]:
    probe = _run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json", str(video_path),
        ]
    )
    if probe.returncode:
        raise VideoError("The video could not be opened")
    try:
        details = json.loads(probe.stdout)
        stream = details["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise VideoError("The video has no usable picture or duration") from exc
    duration = 0.0
    for raw in (details.get("format", {}).get("duration"), stream.get("duration")):
        try:
            candidate = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(candidate) and candidate > 0:
            duration = candidate
            break
    if not duration:
        duration = _duration_from_packets(video_path)
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
        raise VideoError("The video has no usable picture or duration")
    if duration > MAX_DURATION_SECONDS:
        raise VideoError("The video must be 30 seconds or shorter")

    decoded = _run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video_path),
         "-map", "0:v:0", "-f", "null", "-"],
        timeout=60,
    )
    if decoded.returncode or decoded.stderr.strip():
        raise VideoError("The video could not be decoded cleanly")

    frames: list[Frame] = []
    for index in range(FRAME_COUNT):
        timestamp = duration * (index + 0.5) / FRAME_COUNT
        frame_path = work_dir / f"frame_{index:02d}.jpg"
        result = _run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-i", str(video_path),
                "-ss", f"{timestamp:.3f}", "-frames:v", "1",
                "-vf", "scale=640:640:force_original_aspect_ratio=decrease",
                "-q:v", "3", "-y", str(frame_path),
            ]
        )
        if result.returncode or not frame_path.is_file() or not frame_path.stat().st_size:
            raise VideoError("Could not extract enough frames from the video")
        frames.append(Frame(timestamp_seconds=timestamp, path=frame_path))
    return frames

