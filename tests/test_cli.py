"""Tests for the command line scripts, run as real processes."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "bin" / "bandcampsync"
SERVICE = ROOT / "bin" / "bandcampsync-service"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, **(env or {})},
    )


def _files(tmp_path):
    cookies = tmp_path / "cookies.txt"
    # Cookies with no identity fail the sync without making any requests
    cookies.write_text("not-an-identity=1\n")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    return cookies, downloads


def test_version_needs_no_other_arguments():
    result = _run(CLI, "--version")

    assert result.returncode == 0
    assert "BandcampSync version" in result.stdout


@pytest.mark.parametrize("value", ["", "   "])
def test_notify_url_requires_a_value(tmp_path, value):
    cookies, downloads = _files(tmp_path)

    result = _run(CLI, "-c", cookies, "-d", downloads, "--notify-url", value)

    assert result.returncode == 2
    assert "--notify-url requires a value" in result.stderr


def test_notify_url_without_an_argument_is_rejected(tmp_path):
    cookies, downloads = _files(tmp_path)

    result = _run(CLI, "-c", cookies, "-d", downloads, "--notify-url")

    assert result.returncode == 2
    assert "expected one argument" in result.stderr


def test_invalid_notify_header_stops_cli_before_syncing(tmp_path):
    cookies, downloads = _files(tmp_path)

    result = _run(
        CLI, "-c", cookies, "-d", downloads, "-n", "POST http://example.com/ bad -"
    )

    assert result.returncode == 1
    assert "Invalid notify header" in result.stderr
    assert "starting" not in result.stderr


def test_invalid_notify_header_stops_service_at_startup(tmp_path):
    cookies, downloads = _files(tmp_path)

    result = _run(
        SERVICE,
        env={
            "COOKIES_FILE": str(cookies),
            "IGNORES_FILE": str(tmp_path / "ignores.txt"),
            "DIRECTORY": str(downloads),
            "TZ": "UTC",
            "NOTIFY_URL": "POST http://example.com/ bad -",
        },
    )

    assert result.returncode == 1
    assert "Invalid notify header" in result.stderr
    assert "Starting synchronisation" not in result.stderr


@pytest.mark.parametrize(
    "value,expected", [("safari270", "safari270"), ("", ""), (None, "")]
)
def test_service_passes_impersonate_to_options(tmp_path, value, expected):
    cookies, downloads = _files(tmp_path)
    env = {
        "COOKIES_FILE": str(cookies),
        "IGNORES_FILE": str(tmp_path / "ignores.txt"),
        "DIRECTORY": str(downloads),
        "TZ": "UTC",
        "EXIT_AFTER_RUN": "1",
    }
    if value is not None:
        env["IMPERSONATE"] = value
    else:
        os.environ.pop("IMPERSONATE", None)
    # The real script, stopping at the point it hands its options over to sync
    script = (
        "import runpy, sys, bandcampsync\n"
        "def show(options):\n"
        "    print('IMPERSONATE=' + repr(options.impersonate))\n"
        "bandcampsync.do_sync = show\n"
        "sys.argv = [sys.argv[1]]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )

    result = _run("-c", script, SERVICE, env=env)

    assert result.returncode == 0
    assert f"IMPERSONATE={expected!r}" in result.stdout
