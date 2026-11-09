"""Tests for the bandcampsync-service script, run as a real process."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE = Path(__file__).resolve().parent.parent / "bin" / "bandcampsync-service"


def _start_service(tmp_path):
    # Cookies with no identity fail the sync without making any requests
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("not-an-identity=1\n")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    env = {
        **os.environ,
        "COOKIES_FILE": str(cookies),
        "IGNORES_FILE": str(tmp_path / "ignores.txt"),
        "DIRECTORY": str(downloads),
        "TZ": "UTC",
    }
    return subprocess.Popen(
        [sys.executable, str(SERVICE)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
def test_signal_stops_sleeping_service(tmp_path, stop_signal):
    process = _start_service(tmp_path)
    try:
        for line in process.stdout:
            if "Sleeping for" in line:
                break
        process.send_signal(stop_signal)
        output, _ = process.communicate(timeout=5)
    finally:
        process.kill()

    assert process.returncode == 0
    assert "Caught shutdown signal" in output
    assert "Done" in output
