import json
from pathlib import Path
import subprocess

import pytest

from physio_coach import video


def test_extracts_twelve_spread_out_timestamped_frames(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake-video")

    def fake_run(command, timeout=45):
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {"streams": [{"width": 640, "height": 480}],
                     "format": {"duration": "24.0"}}
                ),
                "",
            )
        if command[-1].endswith(".jpg"):
            Path(command[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(video, "_run", fake_run)
    frames = video.extract_frames(source, tmp_path)

    assert len(frames) == 12
    assert frames[0].timestamp_seconds == 1
    assert frames[-1].timestamp_seconds == 23
    assert all(frame.path.is_file() for frame in frames)


def test_rejects_video_over_thirty_seconds(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake-video")
    calls = []

    def fake_run(command, timeout=45):
        calls.append(command[0])
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {"streams": [{"width": 640, "height": 480}],
                 "format": {"duration": "30.1"}}
            ),
            "",
        )

    monkeypatch.setattr(video, "_run", fake_run)

    with pytest.raises(video.VideoError, match="30 seconds"):
        video.extract_frames(source, tmp_path)
    assert calls == ["ffprobe"]


def test_webm_without_container_duration_uses_packet_timestamps(monkeypatch, tmp_path):
    source = tmp_path / "clip.webm"
    source.write_bytes(b"fake-video")

    def fake_run(command, timeout=45):
        if command[0] == "ffprobe" and "packet=pts_time,duration_time" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {"packets": [
                        {"pts_time": "0.0", "duration_time": "0.5"},
                        {"pts_time": "3.5", "duration_time": "0.5"},
                    ]}
                ),
                "",
            )
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {"streams": [{"width": 640, "height": 480}],
                     "format": {"duration": "N/A"}}
                ),
                "",
            )
        if command[-1].endswith(".jpg"):
            Path(command[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(video, "_run", fake_run)
    frames = video.extract_frames(source, tmp_path)

    assert len(frames) == 12
    assert frames[-1].timestamp_seconds < 4

