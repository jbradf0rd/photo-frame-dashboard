#!/usr/bin/env python3
"""Family frame server: serves the built dashboard and a small JSON API.

Stdlib only. Runs in Docker on a home server. LAN only.

  GET  /api/state                  shared family state (shopping, chores, stars, quran, messages, alert)
  POST /api/state/<key>            replace one state key (from the frame; key must be in WRITABLE)
  POST /api/alert   {"text": ...}  show a full-screen alert (needs X-Frame-Token)
  POST /api/alert/dismiss          clear the alert (from the frame)
  POST /api/message {"text": ...}  add a message-board line (needs X-Frame-Token)
  POST /api/message/clear          clear the message board (needs X-Frame-Token)
  GET  /api/weather                Open-Meteo forecast for the house, cached 20 minutes
  GET  /api/calendar               events from the private ICS links in CALENDAR_ICS (cached 10 minutes)
"""
import json
import os
import re
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from zoneinfo import ZoneInfo

import prayer

ROOT = os.environ.get("WEB_ROOT", "/app/web")
DATA = os.environ.get("DATA_DIR", "/app/data")
TOKEN = os.environ.get("FRAME_TOKEN", "")
LAT = float(os.environ["LAT"])
LON = float(os.environ["LON"])
TZ = os.environ.get("TZ_NAME", "UTC")
MADHAB = os.environ.get("MADHAB", "shafi")
ICS = [u for u in os.environ.get("CALENDAR_ICS", "").split() if u]
PORT = int(os.environ.get("PORT", "8098"))

WRITABLE = {"shopping", "chores", "stars", "week", "quran", "volume"}
LOCK = threading.Lock()
STATE_FILE = os.path.join(DATA, "state.json")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    os.makedirs(DATA, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- weather
_weather = {"at": 0, "data": None}


def get_weather():
    if _weather["data"] and time.time() - _weather["at"] < 1200:
        return _weather["data"]
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&hourly=temperature_2m,precipitation_probability,weather_code,is_day"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max,sunrise,sunset"
           "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day"
           "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=%s&forecast_days=7") % (LAT, LON, TZ)
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    _weather.update(at=time.time(), data=data)
    return data


# ---------------------------------------------------------------- calendar (minimal ICS reader)
_cal = {"at": 0, "data": []}


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def _parse_dt(value, params):
    tz = ZoneInfo(TZ)
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", value):
        d = datetime.strptime(value[:8], "%Y%m%d")
        return d.replace(tzinfo=tz), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(tz), False
    m = re.search(r"TZID=([^;:]+)", params)
    zone = ZoneInfo(m.group(1)) if m else tz
    return datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=zone).astimezone(tz), False


def _weekly_rrule(rule, start, end, all_day, window_from, window_to):
    """Expand the common FREQ=WEEKLY / DAILY rules. Other rules give the first instance only."""
    parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
    freq = parts.get("FREQ")
    if freq not in ("WEEKLY", "DAILY"):
        return [(start, end)]
    interval = int(parts.get("INTERVAL", "1"))
    until = None
    if "UNTIL" in parts:
        until, _ = _parse_dt(parts["UNTIL"], "")
    count = int(parts["COUNT"]) if "COUNT" in parts else None
    days = None
    if freq == "WEEKLY" and "BYDAY" in parts:
        names = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        days = {names.index(d[-2:]) for d in parts["BYDAY"].split(",") if d[-2:] in names}
    out, dur, n = [], end - start, 0
    cur = start
    step = timedelta(days=1)
    limit = 800
    while limit and cur <= window_to:
        limit -= 1
        weeks = (cur.date() - start.date()).days // 7
        ok = True
        if freq == "DAILY":
            ok = (cur.date() - start.date()).days % interval == 0
        else:
            ok = weeks % interval == 0 and (cur.weekday() in days if days else cur.weekday() == start.weekday())
        if ok:
            if until and cur > until:
                break
            n += 1
            if count and n > count:
                break
            if cur + dur >= window_from:
                out.append((cur, cur + dur))
        cur += step
    return out


def get_calendar():
    if time.time() - _cal["at"] < 600:
        return _cal["data"]
    tz = ZoneInfo(TZ)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    wfrom, wto = today - timedelta(days=45), today + timedelta(days=60)
    events = []
    for i, url in enumerate(ICS):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                text = _unfold(r.read().decode("utf-8", "replace"))
        except Exception as e:  # keep the last good data for this feed
            print("calendar fetch failed", i, type(e).__name__, flush=True)
            continue
        for block in text.split("BEGIN:VEVENT")[1:]:
            block = block.split("END:VEVENT")[0]
            props = {}
            for line in block.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                name, _, params = k.partition(";")
                props.setdefault(name, (v, params))
            if "DTSTART" not in props:
                continue
            start, all_day = _parse_dt(*props["DTSTART"])
            if "DTEND" in props:
                end, _ = _parse_dt(*props["DTEND"])
            else:
                end = start + (timedelta(days=1) if all_day else timedelta(hours=1))
            title = props.get("SUMMARY", ("(no title)", ""))[0].replace("\\,", ",").replace("\\n", " ")
            loc = props.get("LOCATION", ("", ""))[0].replace("\\,", ",")
            rule = props.get("RRULE", (None, ""))[0]
            spans = _weekly_rrule(rule, start, end, all_day, wfrom, wto) if rule else [(start, end)]
            for s, e in spans:
                if e < wfrom or s > wto:
                    continue
                events.append({"title": title, "loc": loc, "allDay": all_day, "feed": i,
                               "start": s.isoformat(), "end": e.isoformat()})
    _cal.update(at=time.time(), data=events)
    return events


# ---------------------------------------------------------------- prayer times
_prayer = {"at": 0, "data": None}


def get_prayer():
    """Today's and tomorrow's prayer times in the local timezone (TZ)."""
    if _prayer["data"] and time.time() - _prayer["at"] < 300:
        return _prayer["data"]
    tz = ZoneInfo(TZ)
    now = datetime.now(tz)
    days = []
    for off in (0, 1):
        d = (now + timedelta(days=off)).date()
        utc_times = prayer.compute_prayer_times(LAT, LON, d, MADHAB)
        local = {k: v.replace(tzinfo=timezone.utc).astimezone(tz) for k, v in utc_times.items()}
        days.append({
            "date": d.isoformat(),
            "fajr": local["fajr"].strftime("%H:%M"),
            "sunrise": local["sunrise"].strftime("%H:%M"),
            "dhuhr": local["dhuhr"].strftime("%H:%M"),
            "asr": local["asr"].strftime("%H:%M"),
            "maghrib": local["maghrib"].strftime("%H:%M"),
            "isha": local["isha"].strftime("%H:%M"),
            "iso": {
                "fajr": local["fajr"].isoformat(),
                "dhuhr": local["dhuhr"].isoformat(),
                "asr": local["asr"].isoformat(),
                "maghrib": local["maghrib"].isoformat(),
                "isha": local["isha"].isoformat(),
            },
        })
    _prayer.update(at=time.time(), data={"timezone": TZ, "days": days})
    return _prayer["data"]


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            return
        super().log_message(fmt, *args)

    def end_headers(self):
        if self.path.startswith("/api/") or self.path in ("/", "/index.html"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("body too large")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _authed(self):
        return bool(TOKEN) and self.headers.get("X-Frame-Token") == TOKEN

    def do_GET(self):
        p = self.path.split("?")[0]
        try:
            if p == "/api/state":
                with LOCK:
                    st = load_state()
                st.pop("calendarPush", None)
                return self._json(st)
            if p == "/api/weather":
                return self._json(get_weather())
            if p == "/api/prayer":
                return self._json(get_prayer())
            if p == "/api/calendar":
                with LOCK:
                    pushed = load_state().get("calendarPush")
                if pushed:
                    return self._json({"events": pushed.get("events", []), "feeds": 1, "at": pushed.get("at")})
                return self._json({"events": get_calendar(), "feeds": len(ICS)})
            if p == "/api/health":
                return self._json({"ok": True, "time": now_iso()})
        except Exception as e:
            return self._json({"error": type(e).__name__, "detail": str(e)[:200]}, 502)
        return super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            body = self._body()
        except Exception:
            return self._json({"error": "bad json"}, 400)
        with LOCK:
            state = load_state()
            if p.startswith("/api/state/"):
                key = p.rsplit("/", 1)[1]
                if key not in WRITABLE:
                    return self._json({"error": "key not writable"}, 403)
                state[key] = body.get("value")
                state.setdefault("_rev", {})[key] = now_iso()
            elif p == "/api/alert":
                if not self._authed():
                    return self._json({"error": "token"}, 401)
                text = str(body.get("text", "")).strip()[:500]
                if not text:
                    return self._json({"error": "empty"}, 400)
                state["alert"] = {"id": str(int(time.time() * 1000)), "text": text, "at": now_iso()}
            elif p == "/api/alert/dismiss":
                cur = state.get("alert")
                if cur and (not body.get("id") or body.get("id") == cur.get("id")):
                    state["alert"] = None
                    state["alertDismissedAt"] = now_iso()
            elif p == "/api/message":
                if not self._authed():
                    return self._json({"error": "token"}, 401)
                text = str(body.get("text", "")).strip()[:300]
                if not text:
                    return self._json({"error": "empty"}, 400)
                msgs = state.get("messages") or []
                msgs.insert(0, {"id": str(int(time.time() * 1000)), "text": text, "at": now_iso(),
                                "from": str(body.get("from", "Dad"))[:30]})
                state["messages"] = msgs[:5]
            elif p == "/api/calendar/push":
                if not self._authed():
                    return self._json({"error": "token"}, 401)
                evs = body.get("events")
                if not isinstance(evs, list):
                    return self._json({"error": "events must be a list"}, 400)
                state["calendarPush"] = {"at": now_iso(), "events": evs[:1500]}
                save_state(state)
                return self._json({"ok": True, "count": len(evs)})
            elif p == "/api/message/clear":
                if not self._authed():
                    return self._json({"error": "token"}, 401)
                state["messages"] = []
            else:
                return self._json({"error": "not found"}, 404)
            save_state(state)
            return self._json({"ok": True, "state": state})


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    print("family-frame on :%d, web=%s, calendars=%d" % (PORT, ROOT, len(ICS)), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
