# ⛪ Church Service Audio Splitter

An automated, local tool designed for church media teams to take raw church service audio recordings (`.mp3` or `.wav`) and split them into distinct, high-fidelity files for **Worship Music** and the **Sermon**.

---

## ✨ Features

- **🚀 Lossless Cutting with FFmpeg (`-c copy`)**:
  - Direct audio stream copy with **0% audio quality loss** and no re-encoding.
  - Generates split files in milliseconds regardless of service length.
  - Automatically preserves bitrate, sample rate, channels, and metadata tags.

- **🧠 Whisper-Powered Speech Density Detection**:
  - Uses OpenAI Whisper with Voice Activity Detection (VAD) via `faster-whisper`.
  - Computes sliding-window speech density ($T_{\text{speech}} / T_{\text{window}}$) and word cadence across the service.
  - Differentiates worship singing/music from continuous spoken preaching.
  - Automatically bridges short pastor pauses (scripture reading, prayer, congregation response) up to configurable tolerance.

- **🎛️ Dual Interface: Modern Web UI + Rich CLI**:
  - **Interactive Web App**:
    - **Service & Event Selector**: Tailored presets for **Sunday Morning Service (12:00 PM)**, **Sunday School Adult Teaching (11:00 AM)**, **Wednesday Evening Service**, **Friday Evening Service**, and **Revival Meetings**.
    - **Explicit Message Title Input**: Enter the sermon title; it is automatically burned into ID3 tags, file names, and Spotify episode notes.
    - **Multi-Track Service & Song Break Splitter**: Isolate every individual worship song sung, Sunday School lesson, preaching, and altar call.
    - **Selective Track Export**: Check or uncheck tracks, export only preaching, export selected songs, or click `✂️ Export This` on any individual track.
    - **Auto-Detect Song Breaks**: Scans worship sections for musical pauses and splits distinct songs.
    - Interactive speech density timeline canvas with zone color coding.
    - Start & End timestamp inputs and $+/- 1\text{s}, 5\text{s}$ adjustment buttons.
    - Integrated audio player with "Listen Start/End Transition" preview buttons.
    - File upload and local path pickers.
    - Sermon transcript viewer & text export.
    - Option to combine opening and closing worship into a single joined file.
    - **Automated UGREEN NAS Watch Folder**: Monitors incoming Audacity recording exports from the NAS and processes them automatically.
    - **AI Scripture & Spotify Publisher**: Detects referenced Bible verses, key quotes, and formats show notes for Spotify for Creators and church website sharing.
  - **Terminal CLI (`church-split`)**:
    - Colorized progress bars and segment summary tables.
    - Batch and script-friendly execution.

---

## 📁 Output Structure

When splitting a church recording, the tool outputs:

1. `BaseName_01_Worship Song 1.mp3` &mdash; First Worship Song
2. `BaseName_02_Worship Song 2.mp3` &mdash; Second Worship Song
3. `BaseName_03_Preaching - [Message Title].mp3` &mdash; Sermon / Adult Teaching
4. `BaseName_04_Altar Call Worship.mp3` &mdash; Altar Call & Ministry Music
5. `BaseName_05_Closing Prayer.mp3` &mdash; Dismissal & Benediction
6. `BaseName_Sermon_Transcript.txt` &mdash; Spoken sermon text with timestamps
7. `BaseName_split_summary.json` &mdash; Exact timestamp index report

---

## 🚀 Quick Start

### 1. Launch the Interactive Web UI

Double-click `run_church_splitter.bat` or run:

```powershell
.\run_church_splitter.ps1
```

Then open your browser to **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

### 2. Using the Command Line (CLI)

```powershell
# Analyze and perform lossless split
python -m church_splitter.cli split -i "C:\Audio\Sunday_Service.mp3" -o "C:\Audio\Splits"

# Split with higher accuracy model and combined worship export
python -m church_splitter.cli split -i "service.wav" --model small --combine-worship

# Inspect and view detected timestamps without cutting
python -m church_splitter.cli analyze -i "service.mp3"
```

---

## ⚙️ Configuration & Options

| Option | CLI Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| **Model Size** | `--model` | `tiny`, `base`, `small`, `medium` | `base` |
| **Min Sermon Length** | `--min-sermon-min` | Minimum sermon duration in minutes | `10.0` |
| **Speech Threshold** | `--density-threshold` | Active speech ratio needed to qualify as preaching | `0.55` |
| **Gap Tolerance** | `--gap-tolerance` | Max pause (seconds) bridged as continuous sermon | `45.0` |
| **Boundary Cushion**| `--padding` | Extra seconds before/after sermon boundary | `2.0` |
| **Combine Worship** | `--combine-worship` | Create joined full worship audio file | `False` |

---

## 🛠️ Architecture

```
church_audio_splitter/
├── src/church_splitter/
│   ├── config.py              # Auto-detects FFmpeg & model parameters
│   ├── ffmpeg_utils.py        # Lossless stream copy (-c copy) & probe info
│   ├── speech_analyzer.py     # Whisper VAD + rolling speech density detector
│   ├── splitter.py            # High-level orchestrator & exporter
│   ├── cli.py                 # Rich terminal interface
│   └── server.py              # FastAPI Web UI server
├── static/
│   ├── index.html             # Sleek dark-mode web application
│   ├── app.js                 # Interactive timeline canvas & audio player
│   └── style.css              # Custom styling
├── tests/
│   └── test_church_splitter.py
├── run_church_splitter.bat    # 1-click Windows launcher
└── run_church_splitter.ps1    # PowerShell launcher
```
