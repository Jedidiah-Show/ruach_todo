import sys
import types
import unittest
from datetime import datetime
from unittest.mock import patch

import gcal_sync


class FakeResp:
    def __init__(self, status):
        self.status = status


class FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = FakeResp(status)


class FakeRequest:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class FakeEvents:
    def __init__(self, update_error=None, insert_error=None):
        self.update_error = update_error
        self.insert_error = insert_error
        self.updates = []
        self.inserts = []
        self.deletes = []

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return FakeRequest({"id": kwargs["eventId"]}, self.update_error)

    def insert(self, **kwargs):
        self.inserts.append(kwargs)
        return FakeRequest({"id": "new-id"}, self.insert_error)

    def delete(self, **kwargs):
        self.deletes.append(kwargs)
        return FakeRequest({})


class FakeService:
    def __init__(self, events):
        self._events = events

    def events(self):
        return self._events


def fake_error_module():
    module = types.ModuleType("googleapiclient.errors")
    module.HttpError = FakeHttpError
    return module


class SchedulePayloadTests(unittest.TestCase):
    def test_timed_event_uses_device_local_timezone(self):
        payload = gcal_sync._schedule_to_event_times("2026-11-25 09:30")
        self.assertNotIn("Lagos", str(payload))
        dt = datetime.fromisoformat(payload["start"]["dateTime"])
        self.assertIsNotNone(dt.tzinfo)  # offset-aware, not naive or hardcoded Lagos

    def test_all_day_event_and_invalid_input(self):
        payload = gcal_sync._schedule_to_event_times("2026-11-25")
        self.assertEqual(payload["start"], {"date": "2026-11-25"})
        self.assertEqual(payload["end"], {"date": "2026-11-26"})
        self.assertIsNone(gcal_sync._schedule_to_event_times("nonsense"))
        self.assertIsNone(gcal_sync._schedule_to_event_times(""))


class SyncTests(unittest.TestCase):
    def _sync(self, events, tasks):
        errors = fake_error_module()
        with patch.dict(sys.modules, {"googleapiclient.errors": errors}), patch.object(
            gcal_sync, "get_calendar_service", return_value=FakeService(events)
        ):
            return gcal_sync.sync_tasks_to_google_calendar(tasks, "/tmp/unused")

    def test_404_recreates_but_other_errors_do_not(self):
        tasks = [{"title": "A", "schedule": "2026-11-25 09:30", "gcal_event_id": "old", "done": False}]
        count, msg = self._sync(FakeEvents(update_error=FakeHttpError(404)), tasks)
        self.assertEqual((count, tasks[0]["gcal_event_id"]), (1, "new-id"))
        self.assertIn("Synced 1", msg)

        tasks = [{"title": "B", "schedule": "2026-11-25 09:30", "gcal_event_id": "old", "done": False}]
        count, msg = self._sync(FakeEvents(update_error=FakeHttpError(500)), tasks)
        self.assertEqual((count, tasks[0]["gcal_event_id"]), (0, "old"))
        self.assertIn("1 failed", msg)

    def test_unscheduled_task_removes_stale_event(self):
        tasks = [{"title": "C", "schedule": "", "gcal_event_id": "stale", "done": False}]
        events = FakeEvents()
        self._sync(events, tasks)
        self.assertEqual(events.deletes[0]["eventId"], "stale")
        self.assertIsNone(tasks[0]["gcal_event_id"])

    def test_insert_error_keeps_task_unchanged(self):
        tasks = [{"title": "D", "schedule": "09:30", "gcal_event_id": None, "done": False}]
        count, _msg = self._sync(FakeEvents(insert_error=RuntimeError("offline")), tasks)
        self.assertEqual(count, 0)
        self.assertIsNone(tasks[0]["gcal_event_id"])


if __name__ == "__main__":
    unittest.main()
