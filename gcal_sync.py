import os
from datetime import datetime, timedelta


def _schedule_to_event_times(sched: str, default_tz: str = "Africa/Lagos") -> dict | None:
    """Convert normalized schedule string into Google Calendar start/end payload."""
    sched = (sched or "").strip()
    if not sched:
        return None
    try:
        if len(sched) == 16:  # YYYY-MM-DD HH:MM
            start_dt = datetime.strptime(sched, "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=30)
            return {
                "start": {"dateTime": start_dt.isoformat(), "timeZone": default_tz},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": default_tz},
            }
        if len(sched) == 10:  # YYYY-MM-DD (all-day)
            start_date = datetime.strptime(sched, "%Y-%m-%d").date()
            end_date = start_date + timedelta(days=1)
            return {
                "start": {"date": start_date.isoformat()},
                "end": {"date": end_date.isoformat()},
            }
        if len(sched) == 5:  # HH:MM (today)
            today = datetime.now().date()
            t_obj = datetime.strptime(sched, "%H:%M").time()
            start_dt = datetime.combine(today, t_obj)
            end_dt = start_dt + timedelta(minutes=30)
            return {
                "start": {"dateTime": start_dt.isoformat(), "timeZone": default_tz},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": default_tz},
            }
    except ValueError:
        return None
    return None


def get_calendar_service(data_dir: str):
    """Authenticate and return a Google Calendar v3 service, or raise RuntimeError with guidance."""
    try:
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
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise RuntimeError(
                    f"Missing credentials.json in {data_dir}. Download an OAuth Desktop client JSON from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def sync_tasks_to_google_calendar(tasks: list[dict], data_dir: str) -> tuple[int, str]:
    """Create or update Google Calendar events for tasks that have a schedule."""
    scheduled_items = [(i, t) for i, t in enumerate(tasks) if (t.get("schedule") or "").strip()]
    if not scheduled_items:
        return 0, "No scheduled tasks to sync with Google Calendar"

    service = get_calendar_service(data_dir)
    synced = 0

    for _idx, task in scheduled_items:
        times = _schedule_to_event_times(task.get("schedule", ""))
        if not times:
            continue

        status_prefix = "[DONE] " if task.get("done") else ""
        body = {
            "summary": f"{status_prefix}{task['title']}",
            "description": task.get("description", ""),
            **times,
        }

        event_id = task.get("gcal_event_id")
        if event_id:
            try:
                updated = (
                    service.events()
                    .update(calendarId="primary", eventId=event_id, body=body)
                    .execute()
                )
                task["gcal_event_id"] = updated.get("id", event_id)
                synced += 1
                continue
            except Exception:
                # Event may have been deleted remotely; recreate below
                pass

        created = service.events().insert(calendarId="primary", body=body).execute()
        if created.get("id"):
            task["gcal_event_id"] = created["id"]
            synced += 1

    return synced, f"Synced {synced} scheduled task(s) to Google Calendar"
