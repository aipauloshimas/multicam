# Multicam

Turn ONE talking-head take into a **virtual multi-camera edit** prompt for **Google Omni**.

You film a single clip on a single camera. The skill finds the beats of your speech, fills a battle-tested prompt template with four cut timestamps, and Google Omni re-frames your real footage from new camera angles with instant hard cuts — same face, same room, same voice, same lip sync. No second camera, no editing timeline.

## How it works
1. Drop your talking-head video in a folder and ask for the multicam prompt.
2. The skill runs a **preflight check** (`scripts/check_env.py`) and, if anything is missing, explains what it is for and asks permission to install it — so it's plug-and-play.
3. It transcribes your video **word-level** (Whisper, runs locally) to find exactly where each phrase starts and where you breathe.
4. It suggests **4 cut points** on those beats (cuts land on phrase starts, inside breaths, never mid-word) and shows you why.
5. You confirm or adjust the timestamps and the camera angles (left profile, extreme high angle, close-up, and back to the original framing — with presets to swap any of them).
6. It fills the frozen template and saves a ready-to-paste prompt. Upload your clip into Google Omni, select it as the source footage, paste, generate.

## Setup (free and local, no API keys)
The skill checks this for you: `scripts/check_env.py` reports what's missing, what each piece is for, and the install command for your OS — then asks before installing anything. To set it up manually:
- Install **Python 3.8+**.
- Install **ffmpeg** (includes `ffprobe`):
  - macOS: `brew install ffmpeg`
  - Windows: `winget install Gyan.FFmpeg` (or `choco install ffmpeg`)
  - Linux: `sudo apt install ffmpeg`
- Install the Python dependency: `pip install -r requirements.txt`

The first transcription downloads a Whisper model (~460MB for the default `small`) once. Everything else is local: no API key, no account, no paid service. Whisper is multilingual, so it works for any creator's language (the delivered prompt is always English).

## Install the skill
This is a **Claude Code skill**. Clone it into your skills folder:

```bash
git clone https://github.com/aipauloshimas/multicam ~/.claude/skills/multicam
```

(Windows: clone into `C:\Users\<you>\.claude\skills\multicam`.)

Then open Claude Code, drop in your clip and say: **"make the multicam prompt for this video"**.

## The template
The prompt template is frozen on purpose — its strict preservation rules ("do not alter the face... no changes to audio... only the camera position changes") are what keep your identity, room and voice locked while the virtual camera cuts. The skill only ever fills the four `[Xs]` timestamps and, if you ask, swaps the angle descriptions. Everything else ships exactly as validated in production.

## Files
- `SKILL.md` — the skill (workflow, the frozen template, cut-placement rules, angle presets).
- `scripts/check_env.py` — preflight dependency check (reports what's missing and how to install it).
- `scripts/beats.py` — local word-level transcription (Whisper) + speech-beat report + first-guess cut points.
- `requirements.txt` — the single Python dependency (openai-whisper).

## License
MIT. See `LICENSE`.
