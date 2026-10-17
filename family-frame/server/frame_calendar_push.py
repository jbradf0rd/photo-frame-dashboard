"""Push a Google calendar (the primary calendar of the signed-in account) to the family frame.

Run it every 10 minutes from cron or a scheduled task.
Reads an authorized-user token file (GOOGLE_TOKEN_FILE, default google_token.json beside this script)
and posts 45 days back and 60 days
ahead to FAMILY_FRAME_URL/api/calendar/push. Events marked private show as "Busy".
Writes one status line to frame_calendar_push.log beside this script.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_calendar_push.log")
CALENDAR_ID = "primary"


def env(key):
    if os.environ.get(key):
        return os.environ[key]
    with open(os.environ.get("FAMILY_FRAME_ENV", os.path.join(HERE, ".env")), encoding="utf-8") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("missing " + key)


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (dt.datetime.now().isoformat(timespec="seconds"), msg))


def main():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    tok = os.environ.get("GOOGLE_TOKEN_FILE", os.path.join(HERE, "google_token.json"))
    creds = Credentials.from_authorized_user_info(json.load(open(tok, encoding="utf-8")))
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    now = dt.datetime.now(dt.timezone.utc)
    out, page = [], None
    while True:
        r = svc.events().list(calendarId=CALENDAR_ID, singleEvents=True, orderBy="startTime", maxResults=500,
                              timeMin=(now - dt.timedelta(days=45)).isoformat(),
                              timeMax=(now + dt.timedelta(days=60)).isoformat(), pageToken=page).execute()
        for e in r.get("items", []):
            if e.get("status") == "cancelled":
                continue
            s, en = e.get("start", {}), e.get("end", {})
            all_day = "date" in s
            private = e.get("visibility") in ("private", "confidential")
            out.append({
                "title": "Busy" if private else e.get("summary", "(no title)"),
                "loc": "" if private else e.get("location", ""),
                "allDay": all_day,
                "start": (s.get("date") + "T00:00:00") if all_day else s.get("dateTime"),
                "end": (en.get("date") + "T00:00:00") if all_day else en.get("dateTime"),
            })
        page = r.get("nextPageToken")
        if not page:
            break
    req = urllib.request.Request(env("FAMILY_FRAME_URL").rstrip("/") + "/api/calendar/push",
                                 data=json.dumps({"events": out}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Frame-Token": env("FAMILY_FRAME_TOKEN")},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        res = json.load(resp)
    log("OK %d events" % res.get("count", -1))
    print("OK", res.get("count"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FAILED %s %s" % (type(e).__name__, str(e)[:200]))
        print("FAILED", type(e).__name__, str(e)[:200])
        sys.exit(1)
