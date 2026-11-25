"""Background due-task notifier for Android (python-for-android service).

Started from the Kivy app via ServiceNotify.start(activity, data_dir).
The service runs in its own process, reads the shared tasks.json, and posts a
notification for each due task even while the UI is closed.
"""
import os
import time
from datetime import datetime
from os import environ

from todo_logic import is_task_due, load_tasks, save_tasks

DATA_DIR = environ.get("PYTHON_SERVICE_ARGUMENT", "")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json") if DATA_DIR else ""

# A timed partial wake lock prevents the OS from freezing the polling loop.
try:
    from jnius import autoclass

    _context = autoclass("org.kivy.android.PythonService").mService
    _power = _context.getSystemService("power")
    _wake_lock = _power.newWakeLock(1, "ruachtodo:notify")
    _wake_lock.acquire(10 * 60 * 1000)
except Exception:
    _wake_lock = None


def _notify(title, message):
    try:
        from plyer import notification

        notification.notify(
            title=title, message=message, app_name="Ruach To-do", timeout=10
        )
        return True
    except Exception:
        return False


def _check_once():
    tasks = load_tasks(TASKS_FILE)
    if not tasks:
        return
    now = datetime.now()
    changed = False
    for task in tasks:
        if not is_task_due(task, now):
            continue
        body = task.get("description") or f"Scheduled for {task.get('schedule')}"
        if _notify(f"Ruach To-do: {task['title']}", body):
            task["notified"] = True
            changed = True
    if changed:
        save_tasks(tasks, TASKS_FILE)


if not TASKS_FILE:
    raise SystemExit("Notify service started without a data directory")

while True:
    try:
        _check_once()
    except Exception:
        pass
    time.sleep(30)
