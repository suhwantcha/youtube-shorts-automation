import subprocess
from unittest.mock import Mock

import pytest

from tech_shorts import media
from tech_shorts.service import safe_error


def test_real_ffmpeg_reports_progress_and_finishes(tmp_path):
    progress = []
    media.run(["-f", "lavfi", "-i", "color=c=black:s=64x64:d=1", "-c:v", "libx264", tmp_path / "clip.mp4"],
              duration=1, on_progress=progress.append)
    assert progress[-1] == 100


def test_failure_keeps_diagnostics_but_removes_input_url(monkeypatch):
    monkeypatch.setattr(media, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media.subprocess, "run", Mock(return_value=subprocess.CompletedProcess(
        [], 1, b"", b"https://example.com/input?token=secret\nError opening output: No space left on device")))
    with pytest.raises(media.MediaError) as error:
        media.run([])
    assert "No space left on device" in safe_error(error.value)
    assert "secret" not in safe_error(error.value)


def test_timeout_is_visible_and_child_is_killed(monkeypatch):
    process = Mock()
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.poll.return_value = None
    process.communicate.side_effect = [subprocess.TimeoutExpired([], 1, output=b"out_time_us=500000\n"), (b"", b"")]
    monkeypatch.setattr(media, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(media.time, "monotonic", Mock(side_effect=[0, 0, 3]))
    progress = []
    with pytest.raises(media.MediaError, match="제한 시간"):
        media.run([], timeout=2, duration=1, on_progress=progress.append)
    assert progress == [50]
    process.kill.assert_called_once()
