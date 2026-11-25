"""Best-effort background reminders when the GUI is closed.

Android uses a p4a foreground service (services/notify_service.py). Desktop
builds register a per-user OS scheduler that runs the app binary with
``--check-notifications`` once a minute.
"""
import os
import shlex
import subprocess
import sys
from datetime import datetime

TASK_NAME = "RuachTodo Notifications"
CRON_MARKER = "ruachtodo-check-notifications"


def _notify(title, message):
    from plyer import notification

    notification.notify(title=title, message=message, app_name="Ruach To-do", timeout=10)


def check_due_once(data_dir: str) -> int:
    """Check tasks once, notify for due items, and persist the notified flags."""
    from todo_logic import is_task_due, load_tasks, save_tasks

    tasks = load_tasks(os.path.join(data_dir, "tasks.json"))
    now = datetime.now()
    sent = 0
    for task in tasks:
        if not is_task_due(task, now):
            continue
        body = task.get("description") or f"Scheduled for {task.get('schedule')}"
        try:
            _notify(f"Ruach To-do: {task['title']}", body)
            task["notified"] = True
            sent += 1
        except Exception:
            pass
    if sent:
        save_tasks(tasks, os.path.join(data_dir, "tasks.json"))
    return sent


def _windows_installed():
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True
    )
    return result.returncode == 0


def _linux_crontab(lines=None):
    if lines is None:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        lines = result.stdout.splitlines() if result.returncode == 0 else []
    return [line for line in lines if CRON_MARKER not in line]


def is_installed() -> bool:
    if sys.platform == "win32":
        return _windows_installed()
    if sys.platform.startswith("linux"):
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return result.returncode == 0 and any(CRON_MARKER in l for l in result.stdout.splitlines())
    return False


def install(exe_path: str) -> tuple[bool, str]:
    """Register a per-user scheduler entry. Never needs administrator rights."""
    if sys.platform == "win32":
        command = ["schtasks", "/Create", "/TN", TASK_NAME, "/TR",
                   f'"{exe_path}" --check-notifications', "/SC", "MINUTE", "/MO", "1", "/F"]
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode == 0, result.stdout or result.stderr

    if sys.platform.startswith("linux"):
        if not shutil_which("crontab"):
            return False, "crontab is not installed on this system"
        env = "SDL_VIDEODRIVER=dummy "
        display = os.environ.get("DISPLAY")
        dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        if display:
            env += f"DISPLAY={shlex.quote(display)} "
        if dbus:
            env += f"DBUS_SESSION_BUS_ADDRESS={shlex.quote(dbus)} "
        line = (f"* * * * * env {env}{shlex.quote(exe_path)} --check-notifications "
                f">/dev/null 2>&1  # {CRON_MARKER}")
        lines = _linux_crontab() + [line]
        result = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                                capture_output=True, text=True)
        return result.returncode == 0, result.stdout or result.stderr

    return False, f"Background scheduler is not supported on {sys.platform}"


def uninstall() -> tuple[bool, str]:
    if sys.platform == "win32":
        result = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                                capture_output=True, text=True)
        return result.returncode == 0, result.stdout or result.stderr
    if sys.platform.startswith("linux"):
        result = subprocess.run(["crontab", "-"], input="\n".join(_linux_crontab()) + "\n",
                                capture_output=True, text=True)
        return result.returncode == 0, result.stdout or result.stderr
    return False, f"Background scheduler is not supported on {sys.platform}"


def shutil_which(name):
    import shutil

    return shutil.which(name)
