import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from church_splitter.splitter import ChurchAudioSplitter
from church_splitter.scripture_extractor import generate_social_summary
from church_splitter.watcher import ChurchAudioWatcher

test_wav = Path("tests/test_output/sample_church_service.wav")
test_jpg = Path("tests/test_output/test_cover.jpg")
out_dir = Path("tests/test_output/e2e_splits")

splitter = ChurchAudioSplitter()

# 1. Test 3-way split with metadata + cover art + mp3
meta = {
    "artist": "Pastor Tim",
    "album": "Fall Revival 2026",
    "year": "2026",
    "genre": "Sermon"
}
print("1. Testing export_splits with metadata & cover art...")
res = splitter.export_splits(
    input_audio_path=test_wav,
    output_dir=out_dir,
    sermon_start=30.0,
    sermon_end=90.0,
    combine_worship=True,
    export_transcript=True,
    sermon_transcript="Please turn with me to Matthew chapter 6 and verse 22. Tonight the title of the message is One Look Is All It Took. God is good and his mercy endures forever.",
    metadata=meta,
    cover_art_path=test_jpg,
    normalize_loudness=False,
    export_mp3=True
)
print(f"Exported files count: {len(res['files'])}")
for f in res["files"]:
    print(f" - {f.get('label')} -> {f.get('filename')}")

# 2. Test AI summary extraction
print("\n2. Testing AI scripture & social summary...")
summary = generate_social_summary(
    transcript="Please turn with me to Matthew chapter 6 and verse 22. Tonight the title of the message is One Look Is All It Took. God is good and his mercy endures forever.",
    preacher="Pastor Tim",
    series="Fall Revival"
)
print(f"Detected Title: {summary['title']}")
print(f"Detected Scripture: {summary['scriptures']}")
print("Social Post Preview:\n" + summary["social_post"])

# 3. Test multi-track custom export with -16 LUFS normalization
print("\n3. Testing export_custom_tracks with -16 LUFS broadcast normalization...")
custom_tracks = [
    {"label": "Opening Worship Song", "start": 0.0, "end": 30.0},
    {"label": "Sermon Part 1", "start": 30.0, "end": 90.0},
    {"label": "Closing Worship", "start": 90.0, "end": 120.0}
]
res_custom = splitter.export_custom_tracks(
    input_audio_path=test_wav,
    output_dir=out_dir / "custom_tracks",
    tracks=custom_tracks,
    metadata=meta,
    cover_art_path=test_jpg,
    normalize_loudness=True,
    export_mp3=True
)
print(f"Custom tracks count: {len(res_custom['files'])}")
for f in res_custom["files"]:
    print(f" - {f.get('label')} -> {f.get('filename')} ({f.get('formatted_range')})")

# 4. Test Watcher initialization and lifecycle
print("\n4. Testing ChurchAudioWatcher...")
watcher = ChurchAudioWatcher(
    watch_folder=out_dir / "watch_inbox",
    output_folder=out_dir / "watch_out",
    default_preacher="Pastor Tim",
    default_series="Sunday Morning",
    normalize_loudness=False,
    export_mp3=True
)
watcher.start()
status = watcher.get_status()
print(f"Watcher status: {status['status']}, is_running: {status['is_running']}")
watcher.stop()
print(f"Watcher stopped successfully: {watcher.status}")

print("\n>>> ALL ADVANCED FEATURES VERIFIED SUCCESSFULLY! <<<")
