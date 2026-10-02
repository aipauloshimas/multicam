#!/usr/bin/env python3
"""Verify a delivered /multicam prompt against the frozen template.

Usage: python verify_prompt.py <delivered_prompt.txt> [--duration <seconds>]

PASS iff:
  - the head (everything through "Shot sequence:") and the tail ("Critical
    requirements:" onward) match the canonical template in ../SKILL.md
    byte-for-byte;
  - every shot block is `* At [<n.n>s]:` (square brackets kept, one decimal)
    followed by an indented angle description;
  - no `[Xs]` placeholder is left and the timestamps ascend (and, with
    --duration, all fall inside the clip).

Soft reports (never fail): a shot count other than 4 or a last shot that does
not return to the original camera (the checkpoint may override both), an
opening hold under 0.8s, spacing under 0.7s, a last cut later than
duration - 1s, and angle descriptions that are neither the template's nor a
preset from the table (fine when the user asked for a custom angle).
Exit 0 on PASS, 1 on FAIL.
"""
import argparse
import re
import sys
from pathlib import Path

CUT_RE = re.compile(r"^\* At \[(\d+\.\d)s\]:$")
FIRST_HOLD = 0.8      # opening shot holds at least this long
MIN_SPACING = 0.7     # minimum seconds between cuts
TAIL_GUARD = 1.0      # last cut must be <= duration - this
BACK_MARK = "back to the original camera position"


def fail(msg: str):
    print(f"FAIL: {msg}")
    sys.exit(1)


def norm(text: str) -> str:
    """Whitespace-collapsed angle text with the subject words neutralised."""
    t = " ".join(text.split())
    t = re.sub(r"\b(?:man|woman|subject)\b", "SUBJ", t)
    t = re.sub(r"\b(?:his|her|their)\b", "POSS", t)
    return t


def main():
    ap = argparse.ArgumentParser(description="Verify a /multicam prompt against the frozen template")
    ap.add_argument("prompt", type=Path)
    ap.add_argument("--duration", type=float, default=None,
                    help="real video duration in seconds (from beats.py), optional")
    args = ap.parse_args()

    skill_md = (Path(__file__).resolve().parent.parent / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"## The canonical template \(FROZEN\).*?\n```\n(.*?)\n```", skill_md, re.S)
    if not m:
        sys.exit("could not extract the canonical template from SKILL.md")
    template = m.group(1).replace("\r\n", "\n").strip()

    delivered = args.prompt.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()

    marker_head = "Shot sequence:\n\n"
    marker_tail = "\n\nCritical requirements:"
    if marker_head not in template or marker_tail not in template:
        sys.exit("the template in SKILL.md no longer has the expected markers "
                 "('Shot sequence:' and 'Critical requirements:')")
    t_head = template.split(marker_head)[0] + marker_head
    t_tail = marker_tail + template.split(marker_tail)[1]

    if not delivered.startswith(t_head):
        for i, (a, b) in enumerate(zip(t_head.split("\n"), delivered.split("\n")), 1):
            if a != b:
                fail(f"head diverges from the template at line {i}:\n"
                     f"  template : {a!r}\n  delivered: {b!r}")
        fail("head is truncated")
    if not delivered.endswith(t_tail):
        fail("tail (Critical requirements list) diverges from the template")
    if len(delivered) < len(t_head) + len(t_tail):
        fail("prompt is truncated: head and tail overlap")

    middle = delivered[len(t_head):len(delivered) - len(t_tail)].strip()
    chunks = [c for c in re.split(r"\n\n+", middle) if c.strip()]
    if not chunks:
        fail("no shot blocks found after 'Shot sequence:'")

    # allowed angle texts: the template's own blocks plus the presets table
    allowed = set()
    for blk in re.split(r"\n\n+", template.split(marker_head)[1].split(marker_tail)[0].strip()):
        lines = blk.split("\n")
        allowed.add(norm(" ".join(lines[1:])))
    allowed |= {norm(w) for w in re.findall(r"\| `([^`]+)` \|", skill_md)}

    cuts = []      # (time, body)
    for i, chunk in enumerate(chunks, 1):
        lines = chunk.split("\n")
        head_line = lines[0]
        cm = CUT_RE.match(head_line)
        if not cm:
            if re.match(r"^\* At \d", head_line):
                fail(f"block {i}: the square brackets were stripped from {head_line!r}. "
                     f"The validated format keeps them: `* At [4.0s]:`")
            if "[Xs]" in head_line:
                fail(f"block {i}: the timestamp placeholder was never filled: {head_line!r}")
            fail(f"block {i} does not start with `* At [<n.n>s]:` (one decimal, brackets kept): "
                 f"{head_line!r}")
        body = lines[1:]
        if not body:
            fail(f"block {i} ({head_line}) has no angle description")
        for ln in body:
            if not ln.startswith("  "):
                fail(f"block {i} ({head_line}): angle lines must be indented by two spaces, "
                     f"as in the template: {ln!r}")
        cuts.append((float(cm.group(1)), " ".join(s.strip() for s in body)))

    if "[Xs]" in delivered:
        fail("a `[Xs]` placeholder is still present")

    times = [c[0] for c in cuts]
    for i in range(len(times) - 1):
        if not times[i] < times[i + 1]:
            fail(f"timestamps must ascend: [{times[i]}s] then [{times[i + 1]}s]")
    if args.duration is not None and times[-1] >= args.duration:
        fail(f"the last cut [{times[-1]}s] is not inside the {args.duration:.1f}s clip")

    warnings = []
    if len(cuts) != 4:
        warnings.append(f"{len(cuts)} cuts instead of the default 4 (fine only if the user chose that "
                        f"at the checkpoint)")
    if times[0] < FIRST_HOLD - 0.05:
        warnings.append(f"the opening shot holds only {times[0]:.1f}s (rule: at least {FIRST_HOLD}s)")
    for a, b in zip(times, times[1:]):
        if b - a < MIN_SPACING - 0.05:
            warnings.append(f"cuts at {a}s and {b}s are only {b - a:.1f}s apart (rule: at least "
                            f"{MIN_SPACING}s)")
    if args.duration is not None and times[-1] > args.duration - TAIL_GUARD + 0.05:
        warnings.append(f"the last cut [{times[-1]}s] is within {TAIL_GUARD:.0f}s of the end "
                        f"({args.duration:.1f}s)")
    if BACK_MARK not in cuts[-1][1]:
        warnings.append("the last shot does not return to the original camera (fine only if the user "
                        "chose that at the checkpoint)")
    for i, (t, body) in enumerate(cuts, 1):
        if norm(body) not in allowed:
            warnings.append(f"shot {i} [{t}s] is neither one of the template's angles nor a preset "
                            f"(fine if the user asked for a custom angle)")

    print("PASS: template intact outside the mutable zones")
    print(f"cuts: {len(cuts)} -> {times}")
    for i, (t, body) in enumerate(cuts, 1):
        print(f"  {i}. [{t}s]  {body[:70]}")
    for w in warnings:
        print(f"WARNING: {w}")
    sys.exit(0)


if __name__ == "__main__":
    main()
