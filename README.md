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

## Setup on Mac

**1. Install Homebrew** (a free tool that installs other programs).
Open the **Terminal** app, paste this, press Enter, and follow what it says:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Install the programs this needs** (Python, yt-dlp for downloading, ffmpeg for audio, Whisper for speech-to-text):

```
brew install python yt-dlp ffmpeg whisper-cpp
```

**3. Download this project.** At the top of this GitHub page click the green **Code** button, then **Download ZIP**.
Double-click the ZIP in your Downloads folder to unzip it.

**4. Install Claude Code** (needs a Claude account):

```
curl -fsSL https://claude.ai/install.sh | bash
```

**5. Open the project in Claude Code.** In Terminal:

```
cd ~/Downloads/gta-clip-finder-main
claude
```

Then go to [Using it](#using-it).

## Setup on Windows

**1. Install Python.** Go to [python.org/downloads](https://www.python.org/downloads/), download it, and run the
installer. **Tick the box "Add python.exe to PATH"** on the first screen.

**2. Install yt-dlp and ffmpeg.** Open **PowerShell** (Start menu → type "PowerShell") and paste:

```
winget install yt-dlp.yt-dlp Gyan.FFmpeg
```

Then **close PowerShell and open it again** so it can find the new programs.

**3. Download this project.** At the top of this GitHub page click the green **Code** button, then **Download ZIP**.
Right-click the ZIP in your Downloads folder → **Extract All**.

**4. Install Claude Code** (needs a Claude account). In PowerShell:

```
irm https://claude.ai/install.ps1 | iex
```

**5. Open the project in Claude Code.** In PowerShell:

```
cd $HOME\Downloads\gta-clip-finder-main\gta-clip-finder-main
claude
```

(If that folder doesn't exist, look in Downloads for where the ZIP was extracted.)

Whisper itself downloads automatically the first time you run it on Windows.

---

## Using it

In Claude Code, paste a VOD link and say **find clips**, like this:

```
https://www.twitch.tv/videos/1234567890 find clips
```

The first run downloads a couple of helper programs and the speech model (about 1.7 GB, one time only).
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
