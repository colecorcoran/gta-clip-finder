# GTA Clip Finder

The user may not be a coder. Keep replies short and plain-English.
On Windows, use `python` instead of `python3` in the commands below.

## First-time setup (do this automatically before the first "find clips", or when the user says "set up")

If `tools/TwitchDownloaderCLI` (or `tools/TwitchDownloaderCLI.exe` on Windows) or `tools/models/` doesn't exist yet,
this is a first run. Tell the user in one line that you're setting things up first, then:

1. Run `python3 find_clips.py setup` (Windows: `python find_clips.py setup`).
   - If `python3`/`python` isn't found: on Mac run `xcode-select --install` (or `brew install python` if Homebrew
     exists); on Windows run `winget install -e --id Python.Python.3.12`. Then retry.
2. If it exits with "Missing programs", install each one with the command it prints (Mac: `brew install ...`,
   Windows: `winget install ...`), explaining each in plain words (e.g. "yt-dlp downloads the stream's audio").
   - Mac without Homebrew: Homebrew's installer needs the user's Mac password, so you can't run it for them. Ask them
     to type this in the chat themselves (the `!` runs it here), then continue:
     `! /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
     Afterwards, Homebrew may print "Next steps" lines to add it to PATH; run those too.
   - Windows: newly installed programs usually aren't visible until the terminal restarts. If setup still says they're
     missing, ask the user to close and reopen Claude Code in this folder, then say "find clips" again.
3. Re-run `setup` until it ends with "All set up". The first time it downloads TwitchDownloaderCLI and the speech model
   (~1.6 GB, can take several minutes); run it in the background and tell the user.

## When the user pastes a Twitch VOD link and says "find clips"

0. If this is a first run (see above), do the setup first, then continue.
1. Run in the background (usually 3-6 minutes whatever the VOD length: chat download, then ~2 min of audio around each
   of the top 40 spikes is downloaded and transcribed; it does NOT transcribe the whole VOD):
   `python3 find_clips.py analyze "<link>"`
   Tell the user it's running and roughly how long to expect. If it fails, read the error and fix it or explain in plain words.
2. Read `runs/<VOD_ID>/candidates.md` fully (use offset/limit to page through it). It has the top 40 chat spikes, each with
   chat score, the most common chat messages, and what the streamer said from 45s before the spike to its end.
   Chat reacts ~5-15s AFTER something happens, so the actual moment is usually just before the spike window.
3. Pick the 20 best moments for short-form clips (TikTok/Shorts): funny, shocking, or hype. Prefer moments where the
   streamer's own words/reaction carry the clip, not just chat spam or ads. Merge candidates that are the same moment.
   Ignore lines marked "(repeated Nx, likely music/Whisper glitch)". If fewer than 20 are worth it, pick fewer and say so.
   **GTA 6 tuning:** rank these moment types higher (look for them in the transcript and in chat like WASTED, cops,
   5 stars, NPC, glitch, heist): police chases / wanted levels, crazy crashes and wrecks, glitches and broken physics,
   funny NPC moments, and first reactions to new features or new map areas ("wait, you can do THAT?", first time seeing
   a city/location). Say which type it is in the reason line when it fits.
4. Write `runs/<VOD_ID>/data/picks.json`, best first, as a list of:
   `{"moment_seconds": <int, when the moment starts in the VOD>, "reason": "<one line>", "hook": "<short title/hook idea>"}`
5. Run `python3 find_clips.py render <VOD_ID>` to create `runs/<VOD_ID>/moments.md` (it builds the timestamps and links
   that start 20s early). Then show the user the top 5 and the path to moments.md.

## Notes
- Folder layout: `find_clips.py` (the tool), `tools/` (TwitchDownloaderCLI + Whisper model), `runs/<VOD_ID>/` (one folder
  per VOD: `moments.md`, `candidates.md`, and `data/` with chat and per-spike transcripts in `data/transcripts/`).
  Audio pieces are deleted automatically.
- Re-running on the same VOD reuses the saved chat and transcript, so it's instant.
- Hype words, window size, and other settings are at the top of `find_clips.py`.
- Needs Python 3.8+, yt-dlp and ffmpeg. Whisper (whisper.cpp `whisper-cli`): Homebrew on Mac, auto-downloaded into
  `tools/whisper/` on Windows. TwitchDownloaderCLI and the Whisper model are auto-downloaded into `tools/` by `setup`.
- If `analyze` exits with "Missing programs", follow the first-time setup steps above.
- Slow PC (e.g. Windows without a good graphics card, or a piece takes over a minute)? Suggest changing
  `WHISPER_MODEL` at the top of `find_clips.py` to "small" or "base".
