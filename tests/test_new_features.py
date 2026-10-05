import unittest
from pathlib import Path
from church_splitter.scripture_extractor import generate_social_summary
from church_splitter.splitter import ChurchAudioSplitter

class TestNewFeatures(unittest.TestCase):
    def test_social_summary_service_types(self):
        # Test Wednesday
        summary_wed = generate_social_summary(
            transcript="Tonight we are studying the Word in our Wednesday service.",
            preacher="Pastor Tim",
            series="Wednesday Bible Study",
            title="Faith in the Valley",
            service_type="Wednesday Evening Service"
        )
        self.assertIn("Wednesday Evening Service", summary_wed["social_post"])
        self.assertIn("#WednesdayEveningService", summary_wed["social_post"])
        self.assertIn("Faith in the Valley", summary_wed["social_post"])

        # Test Sunday School
        summary_ss = generate_social_summary(
            transcript="Welcome to adult Sunday School class at 11am.",
            preacher="Brother Mike",
            series="Sunday School",
            title="Foundations of Faith",
            service_type="Sunday School (Adult Teaching)"
        )
        self.assertIn("Sunday School (Adult Teaching)", summary_ss["social_post"])
        self.assertIn("#SundaySchoolAdultTeaching", summary_ss["social_post"])
        self.assertIn("Foundations of Faith", summary_ss["social_post"])

        # Test Friday
        summary_fri = generate_social_summary(
            transcript="Praise the Lord for Friday night prayer.",
            preacher="Pastor Tim",
            title="Anointing and Prayer",
            service_type="Friday Evening Service"
        )
        self.assertIn("Friday Evening Service", summary_fri["social_post"])
        self.assertIn("#FridayEveningService", summary_fri["social_post"])

    def test_custom_track_export_with_title_and_track_number(self):
        test_audio = Path("tests/sample_church_service.wav")
        if not test_audio.exists():
            return

        out_dir = Path("tests/test_output/test_selective_splits")
        out_dir.mkdir(parents=True, exist_ok=True)

        tracks = [
            {"label": "Preaching", "start": 30.0, "end": 60.0, "track_number": 6},
            {"label": "Worship Song 2", "start": 10.0, "end": 25.0, "track_number": 2}
        ]

        meta = {
            "title": "One Look Is All It Took",
            "artist": "Pastor Tim",
            "album": "Sunday Morning Service"
        }

        splitter = ChurchAudioSplitter(model_size="tiny")
        results = splitter.export_custom_tracks(
            input_audio_path=test_audio,
            tracks=tracks,
            output_dir=out_dir,
            metadata=meta
        )

        filenames = [f["filename"] for f in results["files"]]
        # Preaching track should have original track_number 06 and include title
        preach_file = next(f for f in results["files"] if "Preaching" in f["label"])
        self.assertIn("06_Preaching - One Look Is All It Took", preach_file["filename"])

        song_file = next(f for f in results["files"] if "Worship Song 2" in f["label"])
        self.assertIn("02_Worship Song 2", song_file["filename"])

if __name__ == "__main__":
    unittest.main()
