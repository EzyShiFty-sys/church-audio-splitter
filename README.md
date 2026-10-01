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
    - Interactive speech density timeline canvas with zone color coding.
    - Start & End timestamp sliders and $+/- 1\text{s}, 5\text{s}$ adjustment buttons.
    - Integrated audio player with "Listen Start/End Transition" preview buttons.
    - File upload and local path pickers.
    - Sermon transcript viewer & text export.
    - Option to combine opening and closing worship into a single joined file.
  - **Terminal CLI (`church-split`)**:
    - Colorized progress bars and segment summary tables.
    - Batch and script-friendly execution.

---

## 📁 Output Structure

When splitting `Sunday_Service.mp3`, the tool outputs:

1. `Sunday_Service_01_Worship_Opening.mp3` &mdash; Prelude & Opening Worship Music
2. `Sunday_Service_02_Sermon.mp3` &mdash; The Sermon / Message
3. `Sunday_Service_03_Worship_Closing.mp3` &mdash; Response Worship, Altar Call & Benediction
4. `Sunday_Service_Full_Worship_Combined.mp3` *(Optional)* &mdash; Losslessly concatenated worship songs
5. `Sunday_Service_Sermon_Transcript.txt` &mdash; Full spoken sermon text with timestamps
6. `Sunday_Service_split_summary.json` &mdash; Metadata report with exact timestamps and durations

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
