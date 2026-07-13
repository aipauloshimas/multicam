---
name: multicam
description: Use when the user drops or points at a local talking-head video and wants the virtual multi-camera / multi-angle edit prompt for Google Omni (one real take turned into hard cuts between virtual camera angles). Triggers on /multicam, "multicam prompt", "multi-angle edit", a dropped .mp4 plus a camera-cuts request. PT examples for reliability: "faz o prompt multicam desse vídeo", "gera os cortes de câmera desse vídeo", "transforma esse take em multi-ângulo".
---

# /multicam: One Take → Virtual Multi-Camera

## Overview

Turns ONE real talking-head take into the proven Google Omni prompt that re-frames it from multiple virtual cameras with hard cuts on the speech beats. The prompt **preserves the uploaded source video** — face, room, audio, lip sync all frozen; only the virtual camera changes. It does NOT describe or regenerate the scene.

Core principle: **the template is frozen; only two zones ever change** — the four `[Xs]` timestamps (always) and the four angle descriptions (only if the user asks).

## Input

Local video file only (the user's own footage). If the user only has a URL (an Instagram link, a Drive link), ask them to save the video as a local file first. If more than one video could be "the video", ask — never guess via `ls -t`.

## Step 0 — Preflight (first run, or on any missing-tool error)

```bash
python "<this skill's base directory>/scripts/check_env.py"
```

It verifies Python 3.8+, ffmpeg, ffprobe and Whisper, and for anything missing it prints what the tool is FOR plus the exact install command for the user's OS. It never installs anything itself — relay what is missing, ask the user for permission, install, then re-run the check. If everything passed recently in this session, skip straight to Step 1.

## Step 1 — Beats

```bash
python "<this skill's base directory>/scripts/beats.py" "<video path>"
```

(The skill's base directory is announced when this skill loads.)

Report the detected `LANGUAGE` and `DURATION` to the user. Flags: `--language <code>` if detection looks wrong, `--force` to retranscribe, `--model medium` for accuracy over speed.

## Step 2 — Refine the 4 cuts (judgment; the script only reports facts)

`NAIVE_CUTS` is a deterministic first guess — **never deliver it unrefined**. Group `WORDS` into spoken phrases and re-derive:

- Opening shot (original camera) holds ≥0.8s before cut 1.
- Cuts land at phrase starts, never mid-word. Whisper may split hyphenated words into two entries ("multi" + "-angle") — treat them as ONE word; never cut between them.
- When a `GAPS` entry (breath/silence) sits next to a phrase boundary, place the cut at the START of the silence: round the previous word's end up to one decimal (word ends 3.98 → cut at 4.0; ends 5.68 → cut at 5.7). Never at the end of the gap.
- The key-message phrase gets the longest hold.
- Pacing: holds run ~1–2.5s. If a shot would exceed ~2.5s while a clean phrase boundary sits inside it, cut there — and spread the 4 cuts across the whole video, never bunched into one stretch.
- Cut 4 always returns to the original camera before the final phrase — the video closes on the opening framing.
- Min spacing ~0.7s; last cut ≤ duration − 1s; timestamps ascending, one decimal.
- Always exactly 4 cuts (5 shots) by default. Video >15s: warn that the technique shines on short hooks, then pick the 4 beats that cover the whole arc. Video <4s: warn that 4 cuts don't fit the spacing rules, present honest options (fewer cuts / forced-frenetic 4) at the checkpoint — the user's choice there overrides the 4-cut default, including dropping shot blocks or reordering angles (e.g. closing on an angle instead of returning to the original camera). `NO_SPEECH`: warn and offer the evenly spaced fallback or abort.

## Step 3 — Present, then MANDATORY checkpoint

Show the user, in this order:
1. Two lines on how it works: the prompt freezes identity/room/audio/lip-sync and only the virtual camera changes, in instant hard cuts — that's why it looks like a real multi-cam shoot of the same moment.
2. Phrase table with time windows.
3. The 4 suggested timestamps, each justified (which phrase the shot covers; which cuts land in breaths).
4. The template below, still with `[Xs]`.

Then ask (AskUserQuestion; plain chat questions if unavailable) **before filling anything**:
- Accept the suggested timestamps, or adjust which ones?
- Keep the 4 default angles, or swap any (offer the presets table)?

Never skip this checkpoint, even if the user seems in a hurry or the beats look obvious.

## Step 4 — Fill and deliver

Mutate ONLY:
- the four `[Xs]` timestamps — replace just the `X`: `[Xs]` becomes `[0.9s]`. The square brackets STAY in the delivered prompt (that is the production-validated format; `At 0.9s:` without brackets is wrong);
- any angle description the user asked to swap (presets below);
- the subject words inside the angle descriptions — "The man"/"his" → "The woman"/"her" or "The subject"/"their", matching whoever is on screen (extract one frame with ffmpeg and look, if unsure).

Deliver the finished prompt in a fenced code block AND save it as `<video basename>_multicam_prompt.txt` next to the video. Close with usage: upload the source video into Google Omni, select it as source footage, paste the prompt. The delivered prompt is ALWAYS in English, whatever language the conversation or the video is in.

## The canonical template (FROZEN)

Reproduce byte-for-byte — line breaks included. Two known quirks are intentional and validated in production: **"a extreme high angle"** (do NOT correct to "an") and the short line **"Hard cut to a close-up of his face. Preserve"**. If it reads odd, it stays.

```
Maintain the original room, environment, lighting, and the person's identity
exactly as they are. Do not alter the face, facial features, hairstyle,
clothing, body proportions, room layout, background objects, or overall
appearance. The room and the person must remain perfectly consistent
throughout the entire video.

Do not modify the dialogue, voice, speech timing, pacing, lip sync, facial
performance, or audio in any way. The spoken content must remain identical to
the source. The only changes should be the virtual camera framing and angle.

Use fast, clean hard cuts between camera angles. Do not morph, blend,
interpolate, zoom, or animate the transition. Every camera change should feel
like an instant cut to another camera while maintaining perfect continuity.

Shot sequence:

* At [Xs]:
  Cut to a left-side profile B-roll style framing. Keep the subject naturally speaking
  to the original conversation while viewed from the left.

* At [Xs]:
  Hard cut to a extreme high angle. The man briefly looks upward toward the
  camera while continuing to speak naturally. Do not change the speech or
  expression beyond the required eye direction.

* At [Xs]:
  Hard cut to a close-up of his face. Preserve
  facial proportions and identity exactly.

* At [Xs]:
  Hard cut back to the original camera position and framing, matching the
  opening shot perfectly.

Critical requirements:

* Preserve the person's face exactly.
* Preserve the room exactly.
* No changes to audio.
* No changes to speech pacing or timing.
* No changes to lip sync.
* No changes to facial identity or room layout.
* Only the camera position changes through hard cuts.
* Every shot should appear as if captured simultaneously by multiple
  professional cameras in the same room.
```

When filling, replace only the `X` inside the brackets. A correctly filled line looks like:

```
* At [4.0s]:
```

`* At 4.0s:` (brackets stripped) is WRONG — the production-validated prompt keeps the square brackets.

## Angle presets (offered at the checkpoint)

Static camera positions only — the template forbids zooms, pans, morphs and animated moves, so never write movement into an angle description.

| Preset | Template-ready wording |
|---|---|
| Right-side profile | `Cut to a right-side profile B-roll style framing. Keep the subject naturally speaking to the original conversation while viewed from the right.` |
| Low angle | `Hard cut to a low angle looking slightly up at the subject, who continues speaking naturally.` |
| Top-down / overhead | `Hard cut to a top-down overhead angle looking down at the subject. Preserve identity and room exactly.` |
| Over-the-shoulder | `Hard cut to an over-the-shoulder framing from behind the subject, revealing what they are facing.` |
| Extreme close-up (eyes) | `Hard cut to an extreme close-up focused on the eyes and upper face. Preserve facial proportions and identity exactly.` |
| Close-up (lips — SIA original) | `Hard cut to an extreme close-up focused on the lips and bottom face. Preserve facial proportions and identity exactly.` |
| Wide (room reveal) | `Hard cut to a wide shot revealing the full room, with the subject centered and still speaking naturally.` |

## Do NOT (observed failure modes this skill exists to prevent)

- Do NOT write a generative scene-description prompt — character sheet, setting paragraph, dialogue transcript, "CAM A/B/C/D" shot lists. That recreates the scene from text and guarantees identity drift. The template preserves the uploaded take; the source video carries the scene.
- Do NOT restructure, reorder, paraphrase, translate, or grammar-fix the template.
- Do NOT cut mid-word, and do NOT hand over `NAIVE_CUTS` without the Step 2 refinement.
- Do NOT change the shot count — always 4 cuts, and cut 4 always returns to the opening framing.
- Do NOT strip the square brackets when filling the timestamps: `* At [5.7s]:` is correct, `* At 5.7s:` is wrong — check all four lines before saving.
- Do NOT skip the checkpoint or deliver before the user answers it.
