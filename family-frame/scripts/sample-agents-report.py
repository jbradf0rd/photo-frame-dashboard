"""Post a sample Hermes report to a family-frame server (for screenshots and testing).

    python scripts/sample-agents-report.py http://127.0.0.1:8098 <FRAME_TOKEN>

Every number and name in it is made up.
"""
import datetime as dt
import json
import sys
import urllib.request

now = dt.datetime.now().astimezone()


def at(minutes):
    return (now + dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")


week_cost = [3.10, 5.85, 2.40, 7.95, 4.20, 1.75, 2.65]
week = []
for i, c in enumerate(week_cost):
    d = (now.date() - dt.timedelta(days=6 - i)).isoformat()
    week.append({"date": d, "sessions": 20 + i * 3, "tokens": int(c * 4_100_000), "cost": c, "calls": 300 + i * 25})

report = {
    "at": at(0),
    "jobs": {"ok": True, "data": {"enabled": 24, "passing": 23, "failing": 1, "paused": 3,
                                  "nextRun": at(4), "lastRun": at(-1), "lastFailure": at(-95)}},
    "usage": {"ok": True, "data": {"today": week[-1], "week": week,
                                   "sources": {"Telegram": 9, "Scheduled": 26, "Desktop": 4},
                                   "weekCost": round(sum(week_cost), 2), "weekTokens": sum(w["tokens"] for w in week)}},
    "fleet": {"ok": True, "data": {"online": 5, "total": 6, "warn": 1, "hosts": [
        {"id": "local", "name": "NAS", "online": True, "overall": "ok", "cpu": 4, "ram": 41, "disk": 63, "temp": 49},
        {"id": "gpu-box", "name": "gpu-box", "online": True, "overall": "ok", "cpu": 38, "ram": 57, "disk": 44, "temp": 61},
        {"id": "workstation", "name": "workstation", "online": True, "overall": "warn", "cpu": 12, "ram": 88, "disk": 71, "temp": 55},
        {"id": "mini", "name": "mini", "online": True, "overall": "ok", "cpu": 6, "ram": 52, "disk": 39, "temp": None},
        {"id": "laptop", "name": "laptop", "online": True, "overall": "ok", "cpu": 3, "ram": 24, "disk": 58, "temp": 44},
        {"id": "pi", "name": "pi", "online": False, "overall": "down", "cpu": None, "ram": None, "disk": None, "temp": None},
    ]}},
    "power": {"ok": True, "data": {"total": {"today": 0.21, "d7": 1.48, "d30": 6.12}, "pricePerKwh": 0.12,
                                   "note": "Measured GPU power only.", "hosts": [
        {"name": "gpu-box", "watts": 95, "today": 0.17, "d7": 1.20, "d30": 4.90, "measured": ["gpu"]},
        {"name": "workstation", "watts": 18, "today": 0.04, "d7": 0.28, "d30": 1.22, "measured": ["gpu"]},
    ]}},
    "long": {"ok": True, "data": {"jobs": [
        {"name": "Book translation", "done": 4120, "total": 12000, "unit": "pages", "eta": at(60 * 30), "updated": at(-3)},
        {"name": "Photo backup", "done": 812, "total": 1000, "unit": "GB", "eta": None, "updated": at(-8)},
    ], "processes": [{"label": "website", "since": at(-60 * 20)}]}},
    "waiting": {"ok": True, "data": {"people": [
        {"label": "Sam", "open": 24, "overdue": 3, "dueWeek": 5, "noDate": 6, "inProgress": 4, "onHold": 2},
        {"label": "Assistant", "open": 11, "overdue": 0, "dueWeek": 2, "noDate": 3, "inProgress": 2, "onHold": 1},
    ], "draftsLabel": "mail drafts, last 30 days", "drafts": 4, "projects": 9, "unassigned": 1,
        "snapshot": at(-60 * 9)}},
}

url, token = sys.argv[1].rstrip("/"), sys.argv[2]
req = urllib.request.Request(url + "/api/agents/push", data=json.dumps(report).encode(),
                             headers={"Content-Type": "application/json", "X-Frame-Token": token}, method="POST")
print(json.load(urllib.request.urlopen(req, timeout=15)))
