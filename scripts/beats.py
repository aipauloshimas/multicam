#!/usr/bin/env python3
"""Word-level speech beats for /multicam.

Transcribes a local video with Whisper (word timestamps), then prints:
  DURATION, LANGUAGE, WORDS (start/end/word), GAPS (silences >= 0.25s),
  NAIVE_CUTS (4 deterministic cut suggestions).

The script reports facts; semantic refinement (phrase meaning) is Claude's job.
Idempotent: reuses <video stem>.json if present unless --force.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

MIN_GAP = 0.25       # silence >= this between words counts as a breath/pause
MIN_SPACING = 0.7    # minimum seconds between suggested cuts
FIRST_CUT_LO = 0.8   # opening shot must hold at least this long
FIRST_CUT_HI = 1.3   # ...and cut 1 should land by about here
TAIL_GUARD = 1.0     # last cut must be <= duration - this

# don't end the opening shot right after a function word (mid-phrase cut)
FUNCTION_WORDS = {
    "the", "a", "an", "to", "of", "in", "on", "at", "and", "or", "but", "if",
    "is", "are", "was", "i", "you", "it", "my", "your", "this", "that", "for",
    "o", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "que", "e",
    "em", "no", "na", "nos", "nas", "pra", "para", "com", "se", "eu", "meu",
    "minha", "seu", "sua", "por", "mais",
}


def is_function_word(word: str) -> bool:
    return word.lower().strip(".,!?;:…") in FUNCTION_WORDS


def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def ffprobe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True)
    if out.returncode != 0:
        die(f"ffprobe failed on {video}:\n{out.stderr.strip()}")
    return float(out.stdout.strip())


def transcribe(video: Path, model: str, language: str | None):
    # single --output_format: whisper's argparse keeps only the last one given,
    # and the word table is read from the JSON (no SRT needed here)
    cmd = ["whisper", str(video), "--model", model, "--word_timestamps", "True",
           "--output_format", "json",
           "--output_dir", str(video.parent)]
    if language:
        cmd += ["--language", language]
    print(f"# transcribing with whisper --model {model} (first run may download the model)...",
          file=sys.stderr)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        die(f"whisper failed:\n{out.stderr.strip()[-2000:]}")


def load_words(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    words = []
    for seg in d.get("segments", []):
        for w in seg.get("words", []):
            words.append({"word": w["word"].strip(),
                          "start": float(w["start"]), "end": float(w["end"])})
    return d.get("language", "unknown"), words


def naive_cuts(words, duration: float):
    """Deterministic first guess: cut 1 ends the opening phrase (~0.8-1.3s),
    remaining cuts land in the largest silences, gaps filled at word starts."""
    lo, hi = 0.5, duration - TAIL_GUARD
    if hi <= lo:  # video too short to place cuts sanely
        return [], True

    # cut 1: word end closest to 1.0s within [FIRST_CUT_LO, FIRST_CUT_HI],
    # skipping function words (a cut right after "the"/"to" lands mid-phrase)
    c1 = None
    in_range = [w for w in words if FIRST_CUT_LO <= w["end"] <= FIRST_CUT_HI]
    candidates = [w["end"] for w in in_range if not is_function_word(w["word"])]
    if not candidates:
        candidates = [w["end"] for w in in_range]
    if candidates:
        c1 = min(candidates, key=lambda t: abs(t - 1.0))
    else:
        after = [w["end"] for w in words if w["end"] > FIRST_CUT_LO]
        c1 = after[0] if after else min(0.9, hi)
    chosen = [round(min(c1, hi), 1)]

    # gaps sorted by size desc; cut lands at the gap start (end of previous word)
    gaps = []
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g >= MIN_GAP:
            gaps.append({"at": a["end"], "size": g, "after": a["word"]})
    for g in sorted(gaps, key=lambda x: -x["size"]):
        if len(chosen) >= 4:
            break
        t = round(g["at"], 1)
        if lo <= t <= hi and all(abs(t - c) >= MIN_SPACING for c in chosen):
            chosen.append(t)

    # fill remainder: midpoint of the largest open interval, snapped to a word start
    starts = sorted(w["start"] for w in words)
    while len(chosen) < 4:
        pts = sorted(chosen)
        intervals = list(zip([lo] + pts, pts + [hi]))
        a, b = max(intervals, key=lambda iv: iv[1] - iv[0])
        if b - a < 2 * MIN_SPACING:
            break  # no room left; report fewer than 4
        mid = (a + b) / 2
        snapped = min(starts, key=lambda s: abs(s - mid)) if starts else mid
        t = round(min(max(snapped, a + MIN_SPACING), b - MIN_SPACING), 1)
        if all(abs(t - c) >= MIN_SPACING for c in chosen):
            chosen.append(t)
        else:
            chosen.append(round(mid, 1))
    return sorted(set(chosen)), False


def main():
    ap = argparse.ArgumentParser(description="Word-level beats for /multicam")
    ap.add_argument("video", type=Path)
    ap.add_argument("--model", default="small", help="whisper model (default: small)")
    ap.add_argument("--language", default=None, help="force language code, e.g. pt, en")
    ap.add_argument("--force", action="store_true", help="retranscribe even if .json exists")
    args = ap.parse_args()

    try:  # Windows consoles may be cp1252; transcripts may not be
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    missing = [t for t in ("ffprobe", "whisper") if not shutil.which(t)]
    if missing:
        die(f"missing required tools: {', '.join(missing)} "
            f"(run scripts/check_env.py for the install commands)")
    if not args.video.exists():
        die(f"video not found: {args.video}")

    duration = ffprobe_duration(args.video)
    json_path = args.video.with_suffix(".json")
    if args.force or not json_path.exists():
        transcribe(args.video, args.model, args.language)
    if not json_path.exists():
        die(f"whisper produced no JSON at {json_path}")

    language, words = load_words(json_path)

    print(f"DURATION: {duration:.2f}")
    print(f"LANGUAGE: {language}")

    if not words:
        print("NO_SPEECH: true")
        step = duration / 5
        even = [round(step * i, 1) for i in range(1, 5) if step * i <= duration - TAIL_GUARD]
        print("NAIVE_CUTS (evenly spaced fallback, no speech to anchor on):")
        for t in even:
            print(f"  {t}")
        return

    print("\nWORDS:")
    for w in words:
        print(f"  {w['start']:6.2f} -> {w['end']:6.2f}  {w['word']}")

    print("\nGAPS (silences >= %.2fs):" % MIN_GAP)
    any_gap = False
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g >= MIN_GAP:
            any_gap = True
            print(f"  after '{a['word']}': {a['end']:.2f} -> {b['start']:.2f}  (gap {g:.2f}s)")
    if not any_gap:
        print("  (none)")

    cuts, too_short = naive_cuts(words, duration)
    if too_short:
        print("\nSHORT_VIDEO: true (no sane room for 4 cuts)")
    print("\nNAIVE_CUTS (deterministic first guess -- refine against phrase meaning):")
    for t in cuts:
        print(f"  {t}")
    if duration > 15:
        print("LONG_VIDEO: true (>15s; pick the 4 beats that cover the whole arc)")


if __name__ == "__main__":
    main()
