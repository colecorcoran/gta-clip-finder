# GTA Clip Finder

Paste a Twitch VOD link, and it finds the best moments to clip for Shorts / TikTok.
It's tuned for GTA 6 streams: police chases, crashes, glitches, funny NPCs and first reactions get ranked higher.

You get a file called `moments.md` with 20 moments. Each one has a timestamp, why it's good, a title idea, and a
Twitch link that jumps to 20 seconds before the moment.

## How it works

1. Downloads the VOD's chat.
2. Finds the 40 moments where chat went crazy (lots of messages, plus bonus points for KEKW, LUL, Pog, W, "clip",
   WASTED, cops, 5 stars, heist, glitch, NPC...).
3. Downloads only about 2 minutes of audio around each of those moments (not the whole stream, no video).
4. Turns that audio into text on your own computer with Whisper (free, nothing is uploaded).
5. [Claude Code](https://claude.com/claude-code) reads what the streamer said at each moment and picks the 20 best.
6. Deletes the audio when it's done.

A typical run takes about 3-6 minutes on a Mac, whatever the stream length.

---

## Quick setup (Claude Code does the rest)

You only do three things yourself. The first time you say "find clips", Claude Code checks your computer and
installs anything missing (yt-dlp, ffmpeg, Whisper, the speech model) for you, explaining each step.

**1. Install Claude Code** (needs a Claude account).

- **Mac:** open the **Terminal** app, paste this and press Enter:
  ```
  curl -fsSL https://claude.ai/install.sh | bash
  ```
- **Windows:** open **PowerShell** (Start menu → type "PowerShell"), paste this and press Enter:
  ```
  irm https://claude.ai/install.ps1 | iex
  ```

**2. Download this project.** At the top of this GitHub page click the green **Code** button, then **Download ZIP**.
Unzip it (Mac: double-click it. Windows: right-click → **Extract All**).

**3. Open the project in Claude Code.**

- **Mac** (in Terminal):
  ```
  cd ~/Downloads/gta-clip-finder-main
  claude
  ```
- **Windows** (in PowerShell):
  ```
  cd $HOME\Downloads\gta-clip-finder-main\gta-clip-finder-main
  claude
  ```
  (If that folder doesn't exist, look in Downloads for where the ZIP was extracted.)

That's it. Go to [Using it](#using-it). Claude Code will ask your permission before installing anything.

**Good to know about the first run:**
- **Mac:** if you don't have [Homebrew](https://brew.sh) (a free tool that installs programs), Claude will give you
  one command to paste, because Homebrew's installer asks for your Mac password.
- **Windows:** after Claude installs programs, it may ask you to close and reopen Claude Code once so Windows can
  find them.
- The speech model is about 1.6 GB, so the very first run takes a few extra minutes.

<details>
<summary><b>Manual setup (if you'd rather install everything yourself)</b></summary>

**Mac:**
1. Install Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
2. `brew install python yt-dlp ffmpeg whisper-cpp`
3. In the project folder: `python3 find_clips.py setup`

**Windows:**
1. Install Python from [python.org/downloads](https://www.python.org/downloads/) and **tick "Add python.exe to PATH"**.
2. In PowerShell: `winget install -e --id yt-dlp.yt-dlp` and `winget install -e --id Gyan.FFmpeg`, then close and
   reopen PowerShell.
3. In the project folder: `python find_clips.py setup` (this also downloads Whisper).

</details>

---

## Using it

In Claude Code, paste a VOD link and say **find clips**, like this:

```
https://www.twitch.tv/videos/1234567890 find clips
```

The first time, Claude sets everything up before it starts (see above).
Your results are saved in `runs/<VOD number>/moments.md`.

## Tips

- **Slow computer?** Open `find_clips.py` in any text editor and change `WHISPER_MODEL = "large-v3-turbo"` to
  `"small"` or `"base"`. Less accurate, much faster. This helps most on Windows PCs without a good graphics card.
- **Change the hype words** in the `HYPE_WORDS` list at the top of `find_clips.py`.
- **No Claude Code?** You can still run the first part yourself:
  `python3 find_clips.py analyze <VOD link>` (use `python` on Windows), then open `runs/<VOD number>/candidates.md`
  and pick your favourite moments by hand.
- The VOD needs to be public, and chat replay has to be available.

## Credits

Built with [TwitchDownloader](https://github.com/lay295/TwitchDownloader),
[yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org) and
[whisper.cpp](https://github.com/ggml-org/whisper.cpp).
