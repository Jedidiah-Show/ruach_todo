import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import background
from todo_logic import load_tasks


class BackgroundTests(unittest.TestCase):
    def test_one_shot_marks_due_tasks_notified(self):
        due = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        tasks = [
            {"title": "Due", "description": "note", "schedule": due,
             "done": False, "notified": False, "gcal_event_id": None},
            {"title": "Later", "description": "", "schedule": "2099-01-01 09:00",
             "done": False, "notified": False, "gcal_event_id": None},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tasks.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(tasks, f)
            sent = []
            with patch.object(background, "_notify", side_effect=lambda t, m: sent.append(t)):
                count = background.check_due_once(tmp)
            self.assertEqual(count, 1)
            self.assertEqual(len(sent), 1)
            saved = load_tasks(path)
            self.assertTrue(saved[0]["notified"])
            self.assertFalse(saved[1]["notified"])

    @patch.object(background.subprocess, "run")
    def test_install_uses_one_minute_schedule(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        with patch.object(background.sys, "platform", "win32"):
            ok, _msg = background.install("C:\\Program Files\\RuachTodo.exe")
        self.assertTrue(ok)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("/SC") + 1], "MINUTE")
        self.assertIn("--check-notifications", command[command.index("/TR") + 1])


if __name__ == "__main__":
    unittest.main()
