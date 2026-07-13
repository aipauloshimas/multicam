#!/usr/bin/env python3
"""
Preflight environment check for the multicam skill.

Run this FIRST. It verifies everything the skill needs and, for anything
missing, explains what it is FOR and prints the exact install command for the
current operating system. It does NOT install anything itself -- it only
reports, so the agent can explain each item and ask the user for permission
before installing. That keeps the skill plug-and-play and safe.

Usage:
    python check_env.py

Exit code 0 if everything is present, 1 if something is missing.
Uses only the Python standard library, so it runs even before
openai-whisper is installed.
"""
import sys
import shutil
import platform
import importlib.util

OS = platform.system()  # 'Windows', 'Darwin' (macOS), or 'Linux'


def ffmpeg_install_cmd():
    if OS == "Windows":
        return "winget install Gyan.FFmpeg   (or: choco install ffmpeg)"
    if OS == "Darwin":
        return "brew install ffmpeg"
    return "sudo apt install ffmpeg   (Debian/Ubuntu; use your distro's package manager otherwise)"


def main():
    # (name, ok, what it is FOR, how to install)
    checks = []

    py_ok = sys.version_info >= (3, 8)
    checks.append((
        f"Python {sys.version_info.major}.{sys.version_info.minor}",
        py_ok,
        "runs the beats script (word-level transcription + cut suggestions)",
        "install Python 3.8+ from https://python.org, then re-run this check",
    ))

    ff_ok = shutil.which("ffmpeg") is not None
    checks.append((
        "ffmpeg",
        ff_ok,
        "decodes the video's audio for Whisper and extracts a frame for the subject check",
        ffmpeg_install_cmd(),
    ))

    fp_ok = shutil.which("ffprobe") is not None
    checks.append((
        "ffprobe",
        fp_ok,
        "reads the video duration so the cut timestamps stay inside the clip",
        ffmpeg_install_cmd() + "  (ffprobe ships with ffmpeg)",
    ))

    wh_cli = shutil.which("whisper") is not None
    wh_mod = importlib.util.find_spec("whisper") is not None
    checks.append((
        "openai-whisper",
        wh_cli or wh_mod,
        "transcribes your speech locally with word-level timestamps (no API key, no upload)",
        "pip install -U openai-whisper   (or: pip install -r requirements.txt)",
    ))

    all_ok = True
    for name, ok, purpose, install in checks:
        mark = "OK " if ok else "MISSING"
        print(f"[{mark}] {name}")
        print(f"        for: {purpose}")
        if not ok:
            all_ok = False
            print(f"        install: {install}")

    if all_ok:
        print("\nAll set. First transcription downloads a Whisper model once (~460MB for the default 'small').")
    else:
        print("\nSomething is missing. Explain each item to the user and ask before installing.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
