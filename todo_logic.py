import json
import os
from datetime import datetime, time


# Accepted input formats -> canonical representation.
# Canonical values keep the original code's wire format ("YYYY-MM-DD HH:MM",
# "YYYY-MM-DD", "HH:MM") so existing saved tasks remain compatible.
SCHEDULE_FORMATS = (
    ("%Y-%m-%d %H:%M", "datetime"),
    ("%Y-%m-%dT%H:%M", "datetime"),
    ("%Y-%m-%d %I:%M %p", "datetime"),
    ("%Y-%m-%dT%I:%M %p", "datetime"),
    ("%Y-%m-%d", "date"),
    ("%H:%M", "time"),
    ("%I:%M %p", "time"),
)

SCHEDULE_HINT = "YYYY-MM-DD HH:MM, YYYY-MM-DD, or HH:MM (AM/PM allowed)"

# All-day tasks remind at a civilised hour instead of exactly at midnight.
ALL_DAY_REMINDER = time(9, 0)


def load_settings(filepath: str) -> dict:
    """Load user UI settings safely."""
    defaults = {"theme": "light"}
    if not filepath or not os.path.exists(filepath):
        return defaults
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("theme") in ("light", "dark"):
            return {"theme": data["theme"]}
        return defaults
    except (OSError, json.JSONDecodeError):
        return defaults


def save_settings(settings: dict, filepath: str) -> bool:
    """Persist user UI settings safely."""
    try:
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def normalize_schedule(schedule: str) -> tuple[bool, str, str]:
    """Validate and normalize schedule text. Returns (is_valid, normalized_str, error_msg)."""
    cleaned = " ".join((schedule or "").strip().split())
    if not cleaned:
        return True, "", ""

    for fmt, kind in SCHEDULE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if kind == "datetime":
            return True, parsed.strftime("%Y-%m-%d %H:%M"), ""
        if kind == "date":
            return True, parsed.strftime("%Y-%m-%d"), ""
        return True, parsed.strftime("%H:%M"), ""

    return False, cleaned, SCHEDULE_HINT


def schedule_due_datetime(schedule: str, now: datetime | None = None) -> datetime | None:
    """Return the local datetime at which a canonical schedule becomes due."""
    sched = (schedule or "").strip()
    ref = now or datetime.now()
    try:
        if len(sched) == 16:  # YYYY-MM-DD HH:MM
            return datetime.strptime(sched, "%Y-%m-%d %H:%M")
        if len(sched) == 10:  # YYYY-MM-DD (all-day)
            due_date = datetime.strptime(sched, "%Y-%m-%d").date()
            return datetime.combine(due_date, ALL_DAY_REMINDER)
        if len(sched) == 5:  # HH:MM (today)
            due_time = datetime.strptime(sched, "%H:%M").time()
            return datetime.combine(ref.date(), due_time)
    except ValueError:
        return None
    return None


def is_task_due(task: dict, now: datetime | None = None) -> bool:
    """Return True if an incomplete, un-notified task's schedule is due at or before `now`."""
    if task.get("done") or task.get("notified"):
        return False
    sched = (task.get("schedule") or "").strip()
    if not sched:
        return False

    ref = now or datetime.now()
    due_dt = schedule_due_datetime(sched, ref)
    return due_dt is not None and ref >= due_dt


def load_tasks(filepath: str) -> list[dict]:
    """Load tasks from JSON file, normalizing all fields safely."""
    if not filepath or not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        cleaned_tasks: list[dict] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("title"), str):
                title = item["title"].strip()
                if title:
                    desc = item.get("description", "")
                    sched = item.get("schedule", "")
                    gcal_id = item.get("gcal_event_id")
                    if isinstance(sched, str):
                        _ok, norm_sched, _err = normalize_schedule(sched)
                        sched = norm_sched
                    else:
                        sched = ""
                    cleaned_tasks.append({
                        "title": title,
                        "done": bool(item.get("done", False)),
                        "description": desc.strip() if isinstance(desc, str) else "",
                        "schedule": sched,
                        "notified": bool(item.get("notified", False)),
                        "gcal_event_id": gcal_id if isinstance(gcal_id, str) and gcal_id else None,
                    })
        return cleaned_tasks
    except (OSError, json.JSONDecodeError):
        return []


def save_tasks(tasks: list[dict], filepath: str) -> bool:
    """Persist tasks to a JSON file. Returns True on success, False on I/O error."""
    try:
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def add_task(
    tasks: list[dict],
    title: str,
    description: str = "",
    schedule: str = "",
) -> str:
    title = title.strip()
    if not title:
        return "Task title cannot be empty"
    if any(task["title"].lower() == title.lower() for task in tasks):
        return f"{title} already exists"

    ok, norm_sched, err = normalize_schedule(schedule)
    if not ok:
        return f"Invalid schedule: {err}"

    tasks.append({
        "title": title,
        "done": False,
        "description": description.strip(),
        "schedule": norm_sched,
        "notified": False,
        "gcal_event_id": None,
    })
    return f"{title} added to to-dos"


def edit_task(
    tasks: list[dict],
    index: int,
    new_title: str,
    new_description: str | None = None,
    new_schedule: str | None = None,
) -> str:
    if not (0 <= index < len(tasks)):
        return "Invalid task number"
    cleaned = new_title.strip()
    if not cleaned:
        return "Task title cannot be empty"
    if any(
        i != index and task["title"].lower() == cleaned.lower()
        for i, task in enumerate(tasks)
    ):
        return f"{cleaned} already exists"

    old_sched = tasks[index].get("schedule", "")
    if new_schedule is not None:
        ok, norm_sched, err = normalize_schedule(new_schedule)
        if not ok:
            return f"Invalid schedule: {err}"
    else:
        norm_sched = old_sched

    old_title = tasks[index]["title"]
    tasks[index]["title"] = cleaned
    if new_description is not None:
        tasks[index]["description"] = new_description.strip()
    tasks[index]["schedule"] = norm_sched
    if norm_sched != old_sched:
        tasks[index]["notified"] = False
    return f"Updated '{old_title}'"


def remove_task(tasks: list[dict], index: int) -> str:
    if 0 <= index < len(tasks):
        removed = tasks.pop(index)
        return f"{removed['title']} has been deleted"
    return "Invalid task number"


def clear_completed(tasks: list[dict]) -> tuple[int, str]:
    """Remove all completed tasks in place; return (removed_count, status_message)."""
    remaining = [task for task in tasks if not task["done"]]
    removed_count = len(tasks) - len(remaining)
    if removed_count == 0:
        return 0, "No completed tasks to clear"
    tasks[:] = remaining
    return removed_count, f"Cleared {removed_count} completed task(s)"


def count_remaining(tasks: list[dict]) -> int:
    return sum(1 for task in tasks if not task["done"])


def get_filtered_tasks(
    tasks: list[dict], mode: str, query: str = ""
) -> list[tuple[int, dict]]:
    """Return (original_index, task) pairs matching status `mode` and search `query`."""
    if mode == "active":
        candidates = [(i, t) for i, t in enumerate(tasks) if not t["done"]]
    elif mode == "done":
        candidates = [(i, t) for i, t in enumerate(tasks) if t["done"]]
    else:
        candidates = list(enumerate(tasks))

    needle = query.strip().lower()
    if not needle:
        return candidates
    return [
        (i, t)
        for i, t in candidates
        if needle in t["title"].lower()
        or needle in t.get("description", "").lower()
        or needle in t.get("schedule", "").lower()
    ]
