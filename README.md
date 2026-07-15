# MediaGrab — mp3/mp4 downloader

A desktop application for downloading music (mp3) and video (mp4) by
link from popular services: **YouTube, YouTube Music, Spotify, TikTok,
X (Twitter), Facebook** — and any other site supported by
[yt-dlp](https://github.com/yt-dlp/yt-dlp) (over a thousand of them).

New services are added with a single plugin file — see
[docs/ADDING_SERVICES.md](docs/ADDING_SERVICES.md).

## Features

- Paste a link → press "➜" → the file lands in your download folder.
- **mp3 / mp4** switch with the active format highlighted in green.
- Slide-out quality panel: 128/192/320 kbps for mp3,
  360p–1080p or "Max" for mp4.
- The **"…"** button picks the download folder; the folder, format and
  quality are **remembered** after the application is closed.
- The left panel selects a service manually, or the "Auto" mode
  detects the service from the link.
- Download history with status: percentage while downloading,
  a check mark for finished items, a red cross for failed ones.
  Double-clicking a history row puts the link back into the input.
- **Right-click on a history row** — a menu with "Open",
  "Show in folder", "Copy link", "Remove from history", and for failed
  downloads — "Why it did not download…" with the reason and an error
  report.
- Files are named **"Artist - Title"** whenever the service provides
  metadata (Spotify, YouTube Music etc.); otherwise the original name
  is kept.
- Downloading the same track again **does not overwrite the file** —
  an index is appended: "Title (2).mp3", "Title (3).mp3"…
- Pasting a link with **Ctrl+V works on any keyboard layout**
  (even when the input is not focused).
- The **👤 button — profile and settings**: name, download folder,
  statistics, history cleanup, data and cookies folders, app version.
- **Signing in to accounts via browser cookies** (X, Facebook,
  YouTube…) — one text file in the cookies folder:
  [docs/COOKIES.md](docs/COOKIES.md).
- **Automatic update checks**: on startup the application compares its
  version with GitHub and suggests running `update.bat` / `./update.sh`
  in the status bar when a new one is out.
- All user data (settings, history, cookies) lives in `~/.mediagrab` —
  **separate from the program**, so updates never overwrite it.
- Several downloads at once (a queue with 2 parallel workers).

## How Spotify support works

Spotify tracks are DRM-protected and cannot be downloaded directly
(doing so would also violate the service's terms). The Spotify plugin
fetches the **track title** through Spotify's public API and downloads
**the same song from YouTube**. That is why only mp3 is available for
Spotify, and the result is the best matching version of the track found
on YouTube.

---

# Installation

Two things are required: **Python 3.10+** and **ffmpeg** (for mp3
conversion and video merging).

## Windows

1. **Install Python**: download it from
   [python.org/downloads](https://www.python.org/downloads/) and run
   the installer. **Make sure to tick the "Add Python to PATH"
   checkbox** at the bottom of the first screen.
2. **Install ffmpeg** (either way works):
   - open Terminal (PowerShell) and run:
     ```
     winget install ffmpeg
     ```
   - or download the archive from
     [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)
     (the `ffmpeg-release-essentials.zip` file), unpack it to e.g.
     `C:\ffmpeg` and add `C:\ffmpeg\bin` to the `PATH` environment
     variable (Settings → System → Advanced system settings →
     Environment Variables).
3. **Download this application**: the green **Code → Download ZIP**
   button on the repository page, then unpack the archive. (Or
   `git clone` if you use git.)
4. **Run `install.bat`** by double-clicking — it creates a virtual
   environment and installs the dependencies.
5. **Launch the application with `start.bat`**.

## macOS

```bash
# 1. Homebrew (if you don't have it yet): https://brew.sh
brew install python ffmpeg

# 2. Download and unpack the repository (Code → Download ZIP), then:
cd path/to/downloader
chmod +x install.sh start.sh update.sh
./install.sh

# 3. Launch:
./start.sh
```

## Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk ffmpeg

cd path/to/downloader
chmod +x install.sh start.sh update.sh
./install.sh   # once
./start.sh     # launch
```

## Checking the installation

```bash
python3 --version   # must be 3.10 or newer (on Windows: python --version)
ffmpeg -version     # must print the ffmpeg version
```

If ffmpeg is missing, the application still starts but shows a warning
in the status bar at the bottom: without ffmpeg neither mp3 nor
high-quality mp4 works.

## Updating the application

Run **`update.bat`** (Windows) or **`./update.sh`** (macOS/Linux) —
the script downloads fresh program files from GitHub and updates
yt-dlp. Settings, history and cookies are not touched (they live in
`~/.mediagrab`, outside the program folder).

No need to check manually: on every start the application compares its
version with GitHub and, when a new one is out, says so in the status
bar at the bottom of the window and in the profile window (the 👤
button).

If downloads stopped working and there is no new version — run
`update.bat`/`update.sh` anyway: it updates yt-dlp, which fixes
breakage after services change their sites.

---

# Usage

1. Copy a video/track link in your browser.
2. Paste it into the top input (Ctrl+V) and press **➜** or Enter.
3. Pick the format with the **mp3 / mp4** buttons under the input;
   clicking the active format again opens the quality panel.
4. The **"…"** button on the right selects where files are saved
   (remembered between runs).
5. Download progress is shown in the list below; finished rows are
   marked with **✓**.

The left panel selects a service manually, but the **"Auto"** mode is
usually enough — the service is detected from the link.

## Downloading with your account (cookies)

18+ posts on X, videos from Facebook groups and other "signed-in only"
content downloads fine once you connect your browser's cookies — a
single text file placed into the cookies folder (the **👤 →
"Cookies folder"** button). Your login and password are never stored.
Step-by-step guide: [docs/COOKIES.md](docs/COOKIES.md).

---

# When a download fails (errors)

When a download ends with an error, **right-click the row →
"Why it failed…"**. A window opens with:

- **what you can do** — a human explanation of the cause and the steps
  to fix it (e.g. "the content is private, sign-in required", "update
  yt-dlp", "network problem");
- **the error text** — the technical message;
- the **"Copy report"** button — copies the full report (link,
  service, program versions, full error text) that you can send to the
  developer;
- full reports are also saved as files: the `logs` folder next to the
  settings (`~/.mediagrab/logs`, on Windows —
  `C:\Users\NAME\.mediagrab\logs`).

Typical causes:

| Symptom | Cause and fix |
| --- | --- |
| Errors on almost every service | yt-dlp is outdated — run `update.bat` / `./update.sh` |
| "ffmpeg" in the error text | ffmpeg is not installed — see the install section for your OS above |
| X (Twitter) won't download | Only public posts are available without signing in. For 18+ and private accounts connect cookies: [docs/COOKIES.md](docs/COOKIES.md) |
| Facebook won't download | Public videos work right away; for group videos connect cookies ([docs/COOKIES.md](docs/COOKIES.md)) |
| "Unsupported URL" | The link points to a profile/search/home page instead of a video/track |
| "429 / Too Many Requests" | The service rate-limited you — wait a few minutes |

---

# Adding a new service

Every service is one small file in `mediagrab/services/`, and a ready
template `_template.py` lives right there. The detailed guide with
examples: [docs/ADDING_SERVICES.md](docs/ADDING_SERVICES.md).

# Inviting another person to the project

Step-by-step guide (adding a collaborator to the GitHub repository and
working via fork + pull request):
[docs/COLLABORATORS.md](docs/COLLABORATORS.md).

# Project structure

```
downloader/
├── run.py                  # application entry point
├── VERSION                 # version number (for the update check)
├── install.bat / start.bat / update.bat # install, launch, update (Windows)
├── install.sh  / start.sh  / update.sh  # same for macOS/Linux
├── requirements.txt        # Python dependencies (yt-dlp)
├── mediagrab/
│   ├── app.py              # application window (Tkinter)
│   ├── engine.py           # download engine (yt-dlp, background threads)
│   ├── config.py           # settings and history (~/.mediagrab/config.json)
│   ├── version.py          # new-version check against GitHub
│   └── services/           # service plugins
│       ├── base.py         # plugin base class (the "blueprint")
│       ├── _template.py    # template for a new service
│       ├── youtube.py, youtube_music.py, spotify.py,
│       ├── tiktok.py, x_twitter.py, facebook.py
└── docs/
    ├── ADDING_SERVICES.md  # how to add a service
    ├── COOKIES.md          # signing in to accounts via cookies
    └── COLLABORATORS.md    # how to invite a collaborator
```

# Important

Only download content you have the rights to (your own material,
freely licensed works and so on). Responsibility for how the
application is used lies with the user — respect the services' terms
and the copyright laws of your country.
