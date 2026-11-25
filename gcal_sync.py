import json
import os
from datetime import datetime, timedelta, timezone


# Schedule strings are device-local wall-clock times. Never hardcode a region:
# the same instant must be used for the in-app reminder and the calendar event.
def _local_tz():
    return datetime.now().astimezone().tzinfo or timezone.utc


def _schedule_to_event_times(sched: str) -> dict | None:
    """Convert a normalized schedule string into a Google Calendar time payload."""
    sched = (sched or "").strip()
    if not sched:
        return None
    try:
        if len(sched) == 16:  # YYYY-MM-DD HH:MM
            start_dt = datetime.strptime(sched, "%Y-%m-%d %H:%M").replace(tzinfo=_local_tz())
            end_dt = start_dt + timedelta(minutes=30)
            return {
                "start": {"dateTime": start_dt.isoformat(), "timeZone": start_dt.tzname()},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": end_dt.tzname()},
            }
        if len(sched) == 10:  # YYYY-MM-DD (all-day)
            start_date = datetime.strptime(sched, "%Y-%m-%d").date()
            end_date = start_date + timedelta(days=1)
            return {
                "start": {"date": start_date.isoformat()},
                "end": {"date": end_date.isoformat()},
            }
        if len(sched) == 5:  # HH:MM (today)
            start_dt = datetime.combine(
                datetime.now().date(),
                datetime.strptime(sched, "%H:%M").time(),
            ).replace(tzinfo=_local_tz())
            end_dt = start_dt + timedelta(minutes=30)
            return {
                "start": {"dateTime": start_dt.isoformat(), "timeZone": start_dt.tzname()},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": end_dt.tzname()},
            }
    except ValueError:
        return None
    return None


def get_calendar_service(data_dir: str):
    """Authenticate and return a Google Calendar v3 service, or raise RuntimeError with guidance."""
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Install google-api-python-client and google-auth-oauthlib to sync Google Calendar."
        ) from exc

    scopes = ["https://www.googleapis.com/auth/calendar.events"]
    token_path = os.path.join(data_dir, "token.json")
    creds_path = os.path.join(data_dir, "credentials.json")

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        except (ValueError, json.JSONDecodeError, OSError):
            creds = None  # corrupt token: fall through to a fresh login below

    if not creds or not creds.valid or not creds.has_scopes(scopes):
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except (RefreshError, OSError):
                creds = None
        if not creds or not creds.valid or not creds.has_scopes(scopes):
            if not os.path.exists(creds_path):
                raise RuntimeError(
                    f"Missing credentials.json in {data_dir}. Download an OAuth Desktop client JSON from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0)

        # Refresh tokens are long-lived credentials: never leave them world-readable.
        tmp_path = token_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as token_file:
            os.chmod(tmp_path, 0o600)
            token_file.write(creds.to_json())
        os.replace(tmp_path, token_path)

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _delete_event(service, event_id: str) -> bool:
    """Delete a calendar event. Return True only when no event remains."""
    from googleapiclient.errors import HttpError

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as exc:
        if exc.resp.status != 404:
            raise
    return True


def sync_tasks_to_google_calendar(tasks: list[dict], data_dir: str) -> tuple[int, str]:
    """Create/update/remove Google Calendar events for scheduled tasks.

    Returns (synced_count, status_message). ``gcal_event_id`` values are written
    directly into the task dicts; the caller must persist them even when only
    some tasks succeeded.
    """
    service = get_calendar_service(data_dir)
    synced = 0
    removed = 0
    failures = 0

    try:
        from googleapiclient.errors import HttpError
    except ImportError:  # service creation already guarantees this import
        HttpError = Exception  # type: ignore[misc,assignment]

    for task in tasks:
        sched = (task.get("schedule") or "").strip()
        event_id = task.get("gcal_event_id")

        if not sched:
            if event_id:
                try:
                    _delete_event(service, event_id)
                    removed += 1
                except Exception:
                    failures += 1
                task["gcal_event_id"] = None
            continue

        times = _schedule_to_event_times(sched)
        if not times:
            failures += 1
            continue

        body = {
            "summary": f"{'[DONE] ' if task.get('done') else ''}{task['title']}",
            "description": task.get("description", ""),
            **times,
        }

        if event_id:
            try:
                service.events().update(
                    calendarId="primary", eventId=event_id, body=body
                ).execute()
                synced += 1
                continue
            except HttpError as exc:
                # Only a 404 means the event was deleted remotely; recreate it.
                # Network/permission errors must NOT create duplicate events.
                if getattr(exc.resp, "status", None) != 404:
                    failures += 1
                    continue
                task["gcal_event_id"] = None

        try:
            created = service.events().insert(calendarId="primary", body=body).execute()
            task["gcal_event_id"] = created.get("id")
            synced += 1
        except Exception:
            failures += 1

    parts = [f"Synced {synced} scheduled task(s)"]
    if removed:
        parts.append(f"removed {removed} stale event(s)")
    if failures:
        parts.append(f"{failures} failed")
    return synced, "; ".join(parts)
