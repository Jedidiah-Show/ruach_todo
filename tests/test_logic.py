import json
import os
import tempfile
import unittest
from datetime import datetime

from todo_logic import (
    add_task,
    clear_completed,
    count_remaining,
    edit_task,
    get_filtered_tasks,
    is_task_due,
    load_settings,
    load_tasks,
    normalize_schedule,
    remove_task,
    save_settings,
    save_tasks,
    schedule_due_datetime,
)


class ScheduleTests(unittest.TestCase):
    def test_normalizes_supported_formats(self):
        cases = {
            "2026-11-25 09:30": "2026-11-25 09:30",
            "2026-11-25T09:30": "2026-11-25 09:30",
            "2026-11-25 09:30 AM": "2026-11-25 09:30",
            "2026-11-25 09:30 PM": "2026-11-25 21:30",
            "2026-11-25": "2026-11-25",
            "09:30": "09:30",
            "9:30 PM": "21:30",
            "  ": "",
        }
        for raw, expected in cases.items():
            ok, normalized, err = normalize_schedule(raw)
            self.assertTrue(ok, f"{raw!r} should be valid: {err}")
            self.assertEqual(normalized, expected)

    def test_rejects_garbage(self):
        ok, _value, err = normalize_schedule("tomorrow-ish")
        self.assertFalse(ok)
        self.assertTrue(err)

    def test_due_checks(self):
        now = datetime(2026, 11, 25, 10, 0)
        self.assertTrue(is_task_due({"schedule": "2026-11-25 09:00"}, now))
        self.assertFalse(is_task_due({"schedule": "2026-11-25 11:00"}, now))
        self.assertEqual(schedule_due_datetime("2026-11-25", now).hour, 9)
        self.assertTrue(is_task_due({"schedule": "2026-11-25"}, now))
        self.assertTrue(is_task_due({"schedule": "09:00"}, now))
        self.assertFalse(is_task_due({"schedule": "11:00"}, now))
        self.assertFalse(is_task_due({"schedule": "09:00", "done": True}, now))
        self.assertFalse(is_task_due({"schedule": "09:00", "notified": True}, now))
        self.assertFalse(is_task_due({"schedule": "not-a-date"}, now))


class TaskTests(unittest.TestCase):
    def test_add_edit_remove_and_persistence(self):
        tasks = []
        self.assertIn("added", add_task(tasks, "Write report", "notes", "9:30 AM"))
        self.assertEqual(tasks[0]["schedule"], "09:30")
        self.assertIn("already exists", add_task(tasks, "write REPORT"))
        self.assertIn("Invalid schedule", add_task(tasks, "Other", "", "someday"))
        self.assertIn("Updated", edit_task(tasks, 0, "Report v2", "new notes", ""))
        self.assertEqual(tasks[0]["title"], "Report v2")
        self.assertEqual(tasks[0]["schedule"], "")

        tasks[0]["notified"] = True
        edit_task(tasks, 0, "Report v2", "", "10:00")
        self.assertFalse(tasks[0]["notified"])

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tasks.json")
            self.assertTrue(save_tasks(tasks, path))
            loaded = load_tasks(path)
            self.assertEqual(loaded, tasks)

        self.assertIn("deleted", remove_task(tasks, 0))
        self.assertEqual(tasks, [])

    def test_clear_completed(self):
        tasks = [
            {"title": "a", "done": True},
            {"title": "b", "done": False},
        ]
        count, msg = clear_completed(tasks)
        self.assertEqual((count, len(tasks)), (1, 1))
        self.assertIn("Cleared 1", msg)


class FilteringAndStorageTests(unittest.TestCase):
    def test_filter_and_search_keep_original_indices(self):
        tasks = [
            {"title": "Buy milk", "description": "from shop", "schedule": "", "done": False},
            {"title": "Fix app", "description": "calendar notes", "schedule": "09:00", "done": True},
            {"title": "Call", "description": "", "schedule": "", "done": False},
        ]
        self.assertEqual([i for i, _ in get_filtered_tasks(tasks, "active")], [0, 2])
        self.assertEqual([i for i, _ in get_filtered_tasks(tasks, "done")], [1])
        self.assertEqual([i for i, _ in get_filtered_tasks(tasks, "all", "calendar")], [1])
        self.assertEqual([i for i, _ in get_filtered_tasks(tasks, "all", "09:00")], [1])
        self.assertEqual(count_remaining(tasks), 2)

    def test_settings_round_trip_and_bad_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "settings.json")
            self.assertTrue(save_settings({"theme": "dark"}, path))
            self.assertEqual(load_settings(path), {"theme": "dark", "font_scale": 1.0, "background_alerts": False})
            with open(path, "w", encoding="utf-8") as f:
                f.write("{bad json")
            self.assertEqual(load_settings(path), {"theme": "light", "font_scale": 1.0, "background_alerts": False})
        self.assertEqual(load_settings("/no/such/file"), {"theme": "light", "font_scale": 1.0, "background_alerts": False})

    def test_load_tasks_ignores_corrupt_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tasks.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([
                    {"title": "valid", "schedule": "9:30 AM", "notified": True, "gcal_event_id": "e1"},
                    {"title": ""},
                    {"no_title": 1},
                    "not a dict",
                ], f)
            tasks = load_tasks(path)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["schedule"], "09:30")
        self.assertTrue(tasks[0]["notified"])
        self.assertEqual(tasks[0]["gcal_event_id"], "e1")


if __name__ == "__main__":
    unittest.main()
