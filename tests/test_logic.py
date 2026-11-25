import os
import tempfile
import unittest
from datetime import datetime

from todo_logic import (
    add_task,
    clear_completed,
    edit_task,
    is_task_due,
    load_tasks,
    normalize_schedule,
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

        self.assertIn("deleted", __import__("todo_logic").remove_task(tasks, 0))
        self.assertEqual(tasks, [])

    def test_clear_completed(self):
        tasks = [
            {"title": "a", "done": True},
            {"title": "b", "done": False},
        ]
        count, msg = clear_completed(tasks)
        self.assertEqual((count, len(tasks)), (1, 1))
        self.assertIn("Cleared 1", msg)


if __name__ == "__main__":
    unittest.main()
