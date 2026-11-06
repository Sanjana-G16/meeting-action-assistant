import json
import tempfile
import unittest
from pathlib import Path

from app import app, analyze_transcript, init_db


class AnalysisTests(unittest.TestCase):
    def test_extracts_only_explicit_owner_deadline_and_decision(self):
        result = analyze_transcript(
            "Decision: We agreed to publish the report. "
            "Maya Chen will send the draft by Friday. "
            "Someone should review the notes."
        )

        self.assertEqual(len(result["decisions"]), 1)
        self.assertEqual(result["action_items"][0]["assigned_to"], "Maya Chen")
        self.assertEqual(result["action_items"][0]["deadline"], "by Friday")
        self.assertEqual(result["action_items"][1]["assigned_to"], "Not specified")
        self.assertEqual(result["action_items"][1]["deadline"], "Not specified")
        self.assertEqual(result["action_items"][1]["status"], "Needs clarification")

    def test_empty_analysis_has_no_invented_decisions_or_actions(self):
        result = analyze_transcript("")

        self.assertEqual(result["decisions"], [])
        self.assertEqual(result["action_items"], [])
        self.assertEqual(result["clarifications"], [])
        self.assertEqual(result["summary"], "No meeting transcript was provided.")


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(
            TESTING=True,
            DATABASE=str(Path(self.temp_dir.name) / "test-meetings.db"),
        )
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_and_demo_transcript_render(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Demo Mode", response.data)
        self.assertIn(b"Product launch planning meeting", response.data)

    def test_empty_submission_shows_validation_message(self):
        response = self.client.post("/analyze", data={"transcript": " "}, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Paste a meeting transcript", response.data)

    def test_analysis_is_saved_opened_and_deleted(self):
        response = self.client.post(
            "/analyze",
            data={"transcript": "Alex will send the notes by Friday."},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        meeting_url = response.headers["Location"]
        detail = self.client.get(meeting_url)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Alex", detail.data)
        self.assertIn(b"Friday", detail.data)

        history = self.client.get("/history")
        self.assertIn(b"1 action items", history.data)

        meeting_id = int(meeting_url.rsplit("/", 1)[1])
        deleted = self.client.post(f"/meetings/{meeting_id}/delete", follow_redirects=True)
        self.assertEqual(deleted.status_code, 200)
        self.assertIn(b"No saved meetings yet", deleted.data)

    def test_missing_meeting_returns_404(self):
        self.assertEqual(self.client.get("/meetings/999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
