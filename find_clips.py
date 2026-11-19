#!/usr/bin/env python3
"""Clip Finder: finds the best clip moments in a Twitch VOD.

Usage (use "python" instead of "python3" on Windows):
  python3 find_clips.py analyze <twitch VOD link or ID>   # steps 1-5: chat, spikes, audio around spikes, transcribe
  python3 find_clips.py render <VOD ID>                   # step 7: turn picks.json into moments.md

Step 6 (picking the 20 best moments) is done by Claude, who reads
runs/<ID>/candidates.md and writes runs/<ID>/data/picks.json.
"""
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # emoji-safe printing on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"
RUNS = ROOT / "runs"
IS_WINDOWS = platform.system() == "Windows"
EXE = ".exe" if IS_WINDOWS else ""
TDL = TOOLS / f"TwitchDownloaderCLI{EXE}"

# ---- Tunable settings -------------------------------------------------------
# Speech-to-text model. "large-v3-turbo" is the most accurate. On a slow PC (or Windows without
# a graphics card) try "small" or "base" for a much faster run.
WHISPER_MODEL = "large-v3-turbo"

WINDOW = 30            # seconds per chat bucket
TOP_N = 40             # how many spikes to send to Claude
MIN_GAP = 60           # spikes closer than this (seconds) count as the same moment
CHAT_DELAY = 10        # chat usually reacts ~10s after something happens
CONTEXT_BEFORE = 45    # seconds of transcript to show before a spike
PIECE_BEFORE = 75      # audio downloaded per spike: from 75s before the spike window...
PIECE_AFTER = 45       # ...to 45s after it starts (2 minutes total)
LINK_LEAD = 20         # Twitch link starts this many seconds before the moment

# Bonus points per message containing these. Matched as whole words.
# Case-insensitive unless listed in CASE_SENSITIVE.
HYPE_WORDS = {
    "KEKW": 1, "LUL": 1, "LOL": 1, "LULW": 1, "OMEGALUL": 1, "LMAO": 1, "LMFAO": 1,
    "Pog": 1, "PogChamp": 1, "POGGERS": 1, "PogU": 1, "Pogge": 1,
    "W": 1,  # also matches W spam like "WW", "WWWW", "Wwwww"
    "clip": 2, "clipped": 2, "clipit": 2,
    # GTA 6
    "WASTED": 1, "cops": 1, "5 stars": 1, "five stars": 1, "5 star": 1,
    "heist": 1, "glitch": 1, "glitched": 1, "glitching": 1, "NPC": 1, "NPCs": 1,
}
CASE_SENSITIVE = {"W"}  # so the letter "w" in normal sentences doesn't count
# -----------------------------------------------------------------------------


def die(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def vod_id_from(arg):
    m = re.search(r"videos/(\d+)", arg) or re.fullmatch(r"\s*(\d+)\s*", arg)
    if not m:
        die(f"Couldn't find a VOD ID in '{arg}'. Expected something like https://www.twitch.tv/videos/123456789")
    return m.group(1)


def hms(seconds):
    s = max(0, int(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def twitch_link(vod_id, seconds):
    s = max(0, int(seconds))
    return f"https://www.twitch.tv/videos/{vod_id}?t={s // 3600}h{s % 3600 // 60}m{s % 60}s"


def run(cmd, quiet=False):
    """Run a program. quiet=True hides its output unless it fails."""
    cmd = [str(c) for c in cmd]
    if not quiet:
        print("   $", " ".join(cmd)[:200])
    try:
        r = subprocess.run(cmd, capture_output=quiet, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        die(f"'{Path(cmd[0]).name}' isn't installed (or isn't on your PATH). See the setup steps in README.md.")
    if r.returncode != 0:
        if quiet:
            print((r.stdout + r.stderr)[-2000:])
        die(f"Command failed: {Path(cmd[0]).name}")


# ---- One-time setup: helper programs and the speech model ---------------------
def download(url, dest, label):
    print(f"⬇️  Downloading {label} (one time)…")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "gta-clip-finder"})
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.replace(dest)


def github_asset(repo, wanted):
    """URL of the newest release file in a GitHub repo whose name matches `wanted`."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=30",
                                 headers={"User-Agent": "gta-clip-finder"})
    with urllib.request.urlopen(req) as r:
        for release in json.load(r):
            for a in release["assets"]:
                if wanted(a["name"]):
                    return a["browser_download_url"]
    die(f"Couldn't find a download for your computer in {repo}. See README.md for manual setup.")


def unzip(zip_path, dest):
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    zip_path.unlink()


def ensure_tdl():
    """TwitchDownloaderCLI downloads the chat. Fetch the right version for this computer."""
    if TDL.exists():
        return
    system, arch = platform.system(), platform.machine().lower()
    arm = arch in ("arm64", "aarch64")
    suffix = {"Darwin": "MacOSArm64" if arm else "MacOS-x64",
              "Windows": "Windows-x64",
              "Linux": "LinuxArm64" if arm else "Linux-x64"}.get(system)
    if not suffix:
        die(f"Unsupported system: {system}")
    url = github_asset("lay295/TwitchDownloader", lambda n: n.startswith("TwitchDownloaderCLI") and n.endswith(f"-{suffix}.zip"))
    zip_path = TOOLS / "tdl.zip"
    download(url, zip_path, "TwitchDownloaderCLI")
    unzip(zip_path, TOOLS)
    if not IS_WINDOWS:
        TDL.chmod(0o755)


def find_whisper():
    """whisper-cli: from Homebrew/PATH on Mac, or downloaded into tools/whisper on Windows."""
    local = next((TOOLS / "whisper").rglob(f"whisper-cli{EXE}"), None) if (TOOLS / "whisper").exists() else None
    if local:
        return local
    found = shutil.which("whisper-cli")
    if found:
        return found
    if IS_WINDOWS:
        url = github_asset("ggml-org/whisper.cpp", lambda n: n == "whisper-bin-x64.zip")
        zip_path = TOOLS / "whisper.zip"
        download(url, zip_path, "Whisper (speech-to-text)")
        unzip(zip_path, TOOLS / "whisper")
        return find_whisper()
    die("Whisper isn't installed. On Mac run:  brew install whisper-cpp")


def ensure_model():
    model = TOOLS / "models" / f"ggml-{WHISPER_MODEL}.bin"
    if not model.exists():
        download(f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{WHISPER_MODEL}.bin",
                 model, f"the '{WHISPER_MODEL}' speech model (large-v3-turbo is ~1.6 GB, this can take a while)")
    return model


# ---- Step 2: downloads ------------------------------------------------------
def download_chat(vod_id, out):
    if out.exists():
        print("✓ Chat already downloaded")
        return
    ensure_tdl()
    print("⬇️  Downloading chat…")
    tmp = out.parent / "tmp"
    tmp.mkdir(exist_ok=True)
    run([TDL, "chatdownload", "--id", vod_id, "-o", out, "--compression", "None",
         "--temp-path", tmp, "--collision", "Overwrite"])
    shutil.rmtree(tmp, ignore_errors=True)


def piece_start(spike_start):
    return max(0, spike_start - PIECE_BEFORE)


def download_pieces(vod_id, starts, audio_dir):
    """Download only ~2 minutes of audio around each spike (one yt-dlp call for all)."""
    sections = []
    for s in starts:
        sections += ["--download-sections", f"*{s}-{s + PIECE_BEFORE + PIECE_AFTER}"]
    print(f"⬇️  Downloading {len(starts)} audio pieces (~2 min each)…")
    audio_dir.mkdir(exist_ok=True)
    run(["yt-dlp", "-f", "Audio_Only/bestaudio/worst", *sections,
         "-o", f"{audio_dir}/piece_%(section_start)d.%(ext)s",
         "--quiet", "--no-warnings", "--progress", f"https://www.twitch.tv/videos/{vod_id}"])


# ---- Step 3: transcription --------------------------------------------------
def transcribe_pieces(vod_id, spikes, data):
    """Transcribe the audio around each spike. Skips pieces already done."""
    tr_dir, audio_dir = data / "transcripts", data / "audio"
    tr_dir.mkdir(exist_ok=True)
    todo = sorted({piece_start(s["start"]) for s in spikes} -
                  {int(p.stem.split("_")[1]) for p in tr_dir.glob("piece_*.json")})
    if not todo:
        print("✓ Already transcribed")
        return
    whisper, model = find_whisper(), ensure_model()
    try:
        download_pieces(vod_id, todo, audio_dir)
        for n, start in enumerate(todo, 1):
            src = next(audio_dir.glob(f"piece_{start}.*"), None)
            if not src:
                die(f"yt-dlp didn't produce the audio piece at {hms(start)}.")
            print(f"📝 Transcribing piece {n}/{len(todo)} ({hms(start)})…")
            wav = audio_dir / f"piece_{start}.wav"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "16000", "-ac", "1", wav], quiet=True)
            run([whisper, "-m", model, "-f", wav, "-l", "auto", "-oj", "-np",
                 "-mc", "0",  # stops Whisper getting stuck repeating a phrase
                 "-of", tr_dir / f"piece_{start}"], quiet=True)
    finally:
        shutil.rmtree(audio_dir, ignore_errors=True)
        print("🧹 Deleted audio pieces")


def load_piece(data, spike_start):
    """Transcript segments for one spike, as (start, end, text) in VOD time."""
    offset = piece_start(spike_start)
    path = data / "transcripts" / f"piece_{offset}.json"
    segs = []
    for s in json.loads(path.read_text(encoding="utf-8")).get("transcription", []):
        text = s["text"].strip()
        if text:
            segs.append((offset + s["offsets"]["from"] / 1000, offset + s["offsets"]["to"] / 1000, text))
    return segs


def transcript_between(segs, start, end):
    """Readable transcript: fragments joined into sentences, repeats collapsed."""
    lines = []  # [start_time, text, repeat_count]
    for a, b, t in segs:
        if b < start or a > end:
            continue
        if lines and lines[-1][1] == t:
            lines[-1][2] += 1          # Whisper sometimes loops on one phrase
        elif lines and lines[-1][2] == 1 and not lines[-1][1].endswith((".", "?", "!")) \
                and len(lines[-1][1]) < 120:
            lines[-1][1] += " " + t    # join fragments into one sentence
        else:
            lines.append([a, t, 1])
    out = [f"[{hms(a)}] {t}" + (f"  (repeated {n}x, likely music/Whisper glitch)" if n > 2 else "")
           for a, t, n in lines]
    return "\n".join(out) if out else "(no speech detected)"


# ---- Step 4: chat spikes ----------------------------------------------------
def hype_bonus(body):
    words = ["W" if re.fullmatch(r"W[Ww]*", w) else w for w in re.findall(r"[A-Za-z0-9]+", body)]
    lower = {w.lower() for w in words}
    exact = set(words)
    bonus, hits = 0, []
    for word, pts in HYPE_WORDS.items():
        if " " in word:  # phrase like "5 stars"
            found = re.search(r"\b" + re.escape(word.lower()) + r"\b", body.lower()) is not None
        else:
            found = word in exact if word in CASE_SENSITIVE else word.lower() in lower
        if found:
            bonus += pts
            hits.append(word)
    return bonus, hits


def find_spikes(chat):
    buckets = {}
    for c in chat["comments"]:
        t = c["content_offset_seconds"]
        body = c["message"]["body"]
        b = buckets.setdefault(int(t // WINDOW), {"msgs": 0, "bonus": 0, "hits": Counter(), "samples": []})
        bonus, hits = hype_bonus(body)
        b["msgs"] += 1
        b["bonus"] += bonus
        b["hits"].update(hits)
        b["samples"].append(body)
    ranked = sorted(buckets.items(), key=lambda kv: kv[1]["msgs"] + kv[1]["bonus"], reverse=True)
    picked = []
    for idx, b in ranked:
        start = idx * WINDOW
        if any(abs(start - p["start"]) < MIN_GAP for p in picked):
            continue  # same moment as a higher spike
        b["start"] = start
        b["score"] = b["msgs"] + b["bonus"]
        picked.append(b)
        if len(picked) == TOP_N:
            break
    return picked


def sample_chat(msgs, n=8):
    # most repeated messages first: shows what chat was reacting to
    common = [m for m, _ in Counter(m.strip() for m in msgs).most_common(n)]
    return " | ".join(m[:60] for m in common)


# ---- Steps 1-5 --------------------------------------------------------------
def analyze(arg):
    vod_id = vod_id_from(arg)
    run_dir = RUNS / vod_id
    data = run_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    chat_path = data / "chat.json"

    download_chat(vod_id, chat_path)
    chat = json.loads(chat_path.read_text(encoding="utf-8"))
    spikes = find_spikes(chat)
    if not spikes:
        die("This VOD has no chat messages, so there are no spikes to look at.")
    transcribe_pieces(vod_id, spikes, data)
    video = chat.get("video", {})
    streamer = chat.get("streamer", {}).get("name", "unknown")
    title = video.get("title", "")

    out = [f"# Candidates for VOD {vod_id}", "",
           f"Streamer: {streamer}  ", f"Title: {title}  ",
           f"Length: {hms(video.get('length', 0))}, {len(chat['comments'])} chat messages", "",
           f"Top {len(spikes)} chat spikes ({WINDOW}s windows, score = messages + hype bonus).",
           f"Chat reacts late, so the transcript starts {CONTEXT_BEFORE}s before each window.", ""]
    cands = []
    for i, s in enumerate(spikes, 1):
        start, end = s["start"], s["start"] + WINDOW
        hits = ", ".join(f"{w}×{n}" for w, n in s["hits"].most_common(6)) or "none"
        cands.append({"candidate": i, "window_start": start, "score": s["score"]})
        out += [f"## Candidate {i}: {hms(start)} to {hms(end)} (score {s['score']}, {s['msgs']} msgs, hype: {hits})",
                f"Chat: {sample_chat(s['samples'])}", "", "```",
                transcript_between(load_piece(data, start), start - CONTEXT_BEFORE, end), "```", ""]
    (run_dir / "candidates.md").write_text("\n".join(out), encoding="utf-8")
    (data / "candidates.json").write_text(json.dumps(
        {"vod_id": vod_id, "streamer": streamer, "title": title, "candidates": cands}, indent=1))
    print(f"\n✅ Done. {len(spikes)} candidates written to {run_dir / 'candidates.md'}")


# ---- Step 7 -----------------------------------------------------------------
def render(arg):
    vod_id = vod_id_from(arg)
    run_dir = RUNS / vod_id
    meta = json.loads((run_dir / "data" / "candidates.json").read_text(encoding="utf-8"))
    picks = json.loads((run_dir / "data" / "picks.json").read_text(encoding="utf-8"))
    title = re.sub(r"[\[\]]", "", meta["title"] or vod_id).strip()
    out = [f"# Best clip moments: {meta['streamer']}", "",
           f"**VOD:** [{title}](https://www.twitch.tv/videos/{vod_id})  ",
           f"Links start about {LINK_LEAD} seconds before each moment.", ""]
    for rank, p in enumerate(picks, 1):
        t = p["moment_seconds"]
        out += [f"## #{rank} at {hms(t)}", "",
                f"- **Hook:** {p['hook']}",
                f"- **Why:** {p['reason']}",
                f"- **Watch:** {twitch_link(vod_id, t - LINK_LEAD)}", ""]
    (run_dir / "moments.md").write_text("\n".join(out), encoding="utf-8")
    print(f"✅ Wrote {run_dir / 'moments.md'} ({len(picks)} moments)")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("analyze", "render"):
        print(__doc__)
        sys.exit(1)
    {"analyze": analyze, "render": render}[sys.argv[1]](sys.argv[2])
