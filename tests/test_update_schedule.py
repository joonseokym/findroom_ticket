import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_schedule


SLOT = {"hh": "09", "mm": "45", "num": 2383, "enable": "Y"}
BRANCHES = {"TEST": {"zizumNum": "22", "themes": {"ROOM": {"themeNum": "66"}}}}


class Morning(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 7, 9, tzinfo=ZoneInfo("Asia/Seoul"))


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.branches = patch.object(update_schedule, "BRANCHES", BRANCHES)
        self.branches.start()
        self.addCleanup(self.branches.stop)

    def test_ready_snapshot_includes_checked_time_and_status(self):
        with patch.object(update_schedule, "fetch_theme_time", return_value={"status": True, "data": [SLOT]}):
            data = update_schedule.build_schedule()
        self.assertIn("checkedAt", data)
        branch = data["branches"]["TEST"]
        self.assertEqual(branch["themes"]["ROOM"][0]["enable"], "Y")
        self.assertEqual(branch["themeStatus"]["ROOM"]["state"], "ready")

    def test_preopening_response_has_explicit_state(self):
        response = {"status": False, "msg": "예약가능시간이 아닙니다. 예약오픈시간 : 11:30"}
        with patch.object(update_schedule, "datetime", Morning), patch.object(
            update_schedule, "fetch_theme_time", return_value=response
        ):
            branch = update_schedule.build_schedule()["branches"]["TEST"]
        self.assertEqual(branch["themeStatus"]["ROOM"], {
            "state": "not_open", "opensAt": "2026-11-07T11:30:00+09:00",
        })

    def test_api_failure_does_not_publish_empty_success(self):
        with patch.object(update_schedule, "fetch_theme_time", return_value={"status": False, "msg": "Unavailable"}):
            with self.assertRaises(RuntimeError):
                update_schedule.build_schedule()

    def test_all_empty_success_responses_are_rejected(self):
        with patch.object(update_schedule, "fetch_theme_time", return_value={"status": True, "data": []}):
            with self.assertRaises(RuntimeError):
                update_schedule.build_schedule()

    def test_malformed_slots_are_rejected(self):
        for slot in ({**SLOT, "num": ""}, {**SLOT, "enable": ""}, {**SLOT, "hh": "25"}):
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                update_schedule.normalize_slot(slot)

    def test_failed_collection_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "schedule.json"
            output.write_text('{"lastGood":true}', encoding="utf-8")
            with patch.object(update_schedule, "Path", return_value=output), patch.object(
                update_schedule, "build_schedule", side_effect=RuntimeError("Network error")
            ):
                with self.assertRaises(RuntimeError):
                    update_schedule.main()
            self.assertEqual(json.loads(output.read_text()), {"lastGood": True})

    def test_network_failure_retries_then_raises(self):
        with patch.object(update_schedule.urllib.request, "urlopen", side_effect=OSError("Network error")) as request, patch.object(update_schedule.time, "sleep"):
            with self.assertRaises(OSError):
                update_schedule.fetch_theme_time("2026-11-13", "22", "66")
            self.assertEqual(request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
