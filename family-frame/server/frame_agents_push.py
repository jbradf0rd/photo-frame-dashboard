"""Push a Hermes status report to the family frame's Agents tab.

Run it every 5 minutes (Task Scheduler with pythonw, or cron) on the machine that runs Hermes.
Collects six cards and posts them to FAMILY_FRAME_URL/api/agents/push:

  jobs     Hermes cron jobs: enabled, passing, failing, paused, next run (counts only)
  usage    Hermes sessions, tokens and cost: today by source, and the last 7 days
  fleet    every host in the homelab monitor: online, CPU, RAM, fullest disk, temperature
  long     long-running work: progress files in hermes/state/frame-progress, plus live
           Hermes background processes
  power    measured power cost per host (the monitor measures GPU power only)
  waiting  open Zoho tasks per person in FRAME_WORK_PEOPLE (from a nightly snapshot), mail drafts;
           shown on the separate Work tab, not on the Agents tab

The frame hangs in a family room, so no card carries a client name, a task title, a mail
subject or a job name. Each card is collected on its own; one failure marks that card
"error" and the rest still go out. Writes one status line to frame_agents_push.log.

    python frame_agents_push.py          collect and push
    python frame_agents_push.py --dry    collect and print the JSON, push nothing
"""
import datetime as dt
import glob
import json
import os
import sqlite3
import sys
import time
import urllib.request

HERMES = os.environ.get("HERMES_HOME") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share"), "hermes")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_agents_push.log")
PROGRESS_DIR = os.path.join(HERMES, "state", "frame-progress")


def setting(key, default=""):
    """Read a setting from the environment, then from the Hermes .env file."""
    if os.environ.get(key):
        return os.environ[key]
    try:
        with open(os.path.join(HERMES, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return default


# Settings (environment or Hermes .env):
#   FRAME_HOMELAB_MCP   URL of the homelab-monitor MCP endpoint (fleet and power cards)
#   FRAME_HOST_LABELS   rename hosts, e.g. "local=NAS,desktop=mini"
#   FRAME_SAFE_CWD      folders whose name may appear for a background process, ";"-separated
#   FRAME_ZOHO_SNAPSHOT JSON list of Zoho tasks (from a nightly snapshot job)
#   FRAME_WORK_PEOPLE   owner-name match and label per Work card, e.g. "Sam=Sam;Alex=Assistant"
#   FRAME_DRAFTS_LABEL  label for the mail-drafts count
#   GOOGLE_TOKEN_FILE   authorized-user token with Gmail read access (drafts count)
HOMELAB_MCP = setting("FRAME_HOMELAB_MCP")
HOST_NAMES = dict(x.split("=", 1) for x in setting("FRAME_HOST_LABELS", "local=NAS").split(",") if "=" in x)
SAFE_CWD_ROOTS = tuple(x.strip().lower() for x in setting("FRAME_SAFE_CWD").split(";") if x.strip())
ZOHO_SNAPSHOT = setting("FRAME_ZOHO_SNAPSHOT")
WORK_PEOPLE = [x.split("=", 1) for x in setting("FRAME_WORK_PEOPLE").split(";") if "=" in x]
DRAFTS_LABEL = setting("FRAME_DRAFTS_LABEL", "mail drafts, last 30 days")
GOOGLE_TOKEN = setting("GOOGLE_TOKEN_FILE", os.path.join(HERMES, "google_ws_token.json"))


def env(key):
    if os.environ.get(key):
        return os.environ[key]
    with open(os.path.join(HERMES, ".env"), encoding="utf-8") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("missing " + key)


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (dt.datetime.now().isoformat(timespec="seconds"), msg))


def iso(ts):
    return dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds") if ts else None


# ---------------------------------------------------------------- 1. cron jobs
def card_jobs():
    jobs = json.load(open(os.path.join(HERMES, "cron", "jobs.json"), encoding="utf-8"))["jobs"]
    on = [j for j in jobs if j.get("enabled")]
    failing = [j for j in on if (j.get("last_status") not in (None, "ok")) or (j.get("failure_streak") or 0) > 0]
    nxt = sorted(j["next_run_at"] for j in on if j.get("next_run_at"))
    ran = sorted(j["last_run_at"] for j in on if j.get("last_run_at"))
    fail_times = sorted(j["last_run_at"] for j in failing if j.get("last_run_at"))
    return {
        "enabled": len(on), "passing": len(on) - len(failing), "failing": len(failing),
        "paused": len(jobs) - len(on),
        "nextRun": nxt[0] if nxt else None, "lastRun": ran[-1] if ran else None,
        "lastFailure": fail_times[-1] if fail_times else None,
    }


# ---------------------------------------------------------------- 2. Hermes usage
SOURCE_LABEL = {"telegram": "Telegram", "cron": "Scheduled", "desktop": "Desktop", "cli": "Terminal",
                "api_server": "Desktop", "local": "Desktop"}


def card_usage():
    c = sqlite3.connect("file:%s?mode=ro" % os.path.join(HERMES, "state.db"), uri=True, timeout=10)
    today = dt.date.today()
    start = dt.datetime.combine(today - dt.timedelta(days=6), dt.time()).timestamp()
    rows = c.execute(
        "select date(started_at,'unixepoch','localtime') d, source, count(*),"
        " sum(coalesce(input_tokens,0)+coalesce(output_tokens,0)+coalesce(cache_read_tokens,0)+coalesce(cache_write_tokens,0)),"
        " sum(coalesce(actual_cost_usd,estimated_cost_usd,0)), sum(coalesce(api_call_count,0))"
        " from sessions where started_at >= ? group by d, source", (start,)).fetchall()
    c.close()
    days = {}
    for i in range(7):
        d = (today - dt.timedelta(days=6 - i)).isoformat()
        days[d] = {"date": d, "sessions": 0, "tokens": 0, "cost": 0.0, "calls": 0}
    by_source = {}
    for d, src, n, tok, cost, calls in rows:
        if d not in days:
            continue
        x = days[d]
        x["sessions"] += n
        x["tokens"] += tok or 0
        x["cost"] = round(x["cost"] + (cost or 0), 2)
        x["calls"] += calls or 0
        if d == today.isoformat():
            lab = SOURCE_LABEL.get(src, (src or "Other").title())
            by_source[lab] = by_source.get(lab, 0) + n
    week = list(days.values())
    return {"today": week[-1], "week": week, "sources": by_source,
            "weekCost": round(sum(x["cost"] for x in week), 2), "weekTokens": sum(x["tokens"] for x in week)}


# ---------------------------------------------------------------- 3 and 5. homelab monitor (MCP)
class MCP:
    def __init__(self, url):
        self.url, self.sid, self.n = url, None, 0

    def _post(self, payload, want_reply=True):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["mcp-session-id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            self.sid = r.headers.get("mcp-session-id") or self.sid
            body = r.read().decode("utf-8", "replace")
        if not want_reply:
            return None
        if body.lstrip().startswith("{"):
            return json.loads(body)
        for line in body.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if "result" in msg or "error" in msg:
                    return msg
        raise RuntimeError("no reply from MCP")

    def start(self):
        self.n += 1
        self._post({"jsonrpc": "2.0", "id": self.n, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "frame-agents-push", "version": "1"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, want_reply=False)

    def call(self, tool, args=None):
        self.n += 1
        msg = self._post({"jsonrpc": "2.0", "id": self.n, "method": "tools/call",
                          "params": {"name": tool, "arguments": args or {}}})
        if "error" in msg:
            raise RuntimeError(str(msg["error"])[:200])
        text = "".join(b.get("text", "") for b in msg["result"].get("content", []))
        return json.loads(text)


def card_fleet(mcp):
    data = mcp.call("list_hosts")
    out = []
    for h in data.get("hosts", []):
        v = h.get("vitals") or {}
        out.append({
            "id": h.get("name"),
            "name": HOST_NAMES.get(h.get("name"), h.get("name")),
            "online": bool(h.get("online")), "overall": h.get("overall") or "unknown",
            "cpu": v.get("cpu_pct"), "ram": v.get("ram_pct"),
            "disk": (v.get("fullest_disk") or {}).get("pct"), "temp": v.get("cpu_temp_c"),
            "upDays": round((v.get("uptime_sec") or 0) / 86400, 1),
            "seen": iso(h.get("last_seen_ts")),
        })
    return {"hosts": out, "online": sum(1 for h in out if h["online"]), "total": len(out),
            "warn": sum(1 for h in out if h["overall"] not in ("ok",))}


def card_power(mcp, hosts):
    rows, tot = [], {"today": 0.0, "d7": 0.0, "d30": 0.0}
    for h in hosts:
        args = {"range": "30d"}
        if h["id"] != "local":
            args["host"] = h["id"]
        c = mcp.call("get_costs", args)
        m = c.get("machine") or {}
        cost = m.get("cost") or {}
        row = {"name": h["name"], "watts": (m.get("now_w") or {}).get("total"),
               "today": cost.get("today") or 0, "d7": cost.get("d7") or 0, "d30": cost.get("d30") or 0,
               "measured": m.get("measured") or []}
        for k in tot:
            tot[k] = round(tot[k] + row[k], 2)
        rows.append(row)
        price = (c.get("tariff") or {}).get("price_day")
    rows.sort(key=lambda r: -r["d30"])
    return {"hosts": rows, "total": tot, "pricePerKwh": price,
            "note": "Measured GPU power only. CPU and the rest of each machine are not metered."}


# ---------------------------------------------------------------- 4. long jobs
def _alive(pid):
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return False


def card_long():
    jobs = []
    for p in sorted(glob.glob(os.path.join(PROGRESS_DIR, "*.json"))):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        upd = j.get("updated") or iso(os.path.getmtime(p))
        jobs.append({"name": str(j.get("name") or os.path.basename(p)[:-5])[:40],
                     "done": j.get("done"), "total": j.get("total"), "unit": str(j.get("unit") or "")[:20],
                     "eta": j.get("eta"), "updated": upd, "state": j.get("state") or "running"})
    procs = []
    try:
        for p in json.load(open(os.path.join(HERMES, "processes.json"), encoding="utf-8")):
            if not _alive(p.get("pid")):
                continue
            cwd = (p.get("cwd") or "").rstrip("\\/")
            label = os.path.basename(cwd) if SAFE_CWD_ROOTS and cwd.lower().startswith(SAFE_CWD_ROOTS) else "other work"
            procs.append({"label": label or "other work", "since": iso(p.get("started_at"))})
    except FileNotFoundError:
        pass
    return {"jobs": jobs, "processes": procs}


# ---------------------------------------------------------------- 6. work waiting
def _drafts():
    """Mail drafts dated in the last 30 days."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.load(open(GOOGLE_TOKEN, encoding="utf-8")))
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    n, page = 0, None
    while True:
        r = svc.users().drafts().list(userId="me", q="newer_than:30d", maxResults=500, pageToken=page).execute()
        n += len(r.get("drafts", []))
        page = r.get("nextPageToken")
        if not page:
            return n


def card_waiting():
    if not ZOHO_SNAPSHOT:
        raise RuntimeError("FRAME_ZOHO_SNAPSHOT is not set")
    rows = json.load(open(ZOHO_SNAPSHOT, encoding="utf-8"))
    today = dt.datetime.now(dt.timezone.utc).isoformat()
    open_ = [t for t in rows if not t.get("is_completed")]

    week = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat()

    def mine(name):
        ts = [t for t in open_ if any(name in (o or "") for o in (t.get("owners") or []))]
        active = [t for t in ts if t.get("status") != "On Hold"]
        return {"open": len(ts),
                "overdue": sum(1 for t in active if t.get("end_date") and t["end_date"] < today),
                "dueWeek": sum(1 for t in active if t.get("end_date") and today <= t["end_date"] < week),
                "noDate": sum(1 for t in active if not t.get("end_date")),
                "inProgress": sum(1 for t in ts if t.get("status") == "In Progress"),
                "onHold": sum(1 for t in ts if t.get("status") == "On Hold")}
    people = []
    for match, label in WORK_PEOPLE:
        x = mine(match.strip())
        x["label"] = label.strip()
        people.append(x)
    out = {"people": people, "draftsLabel": DRAFTS_LABEL,
           "projects": len({t.get("project_id") for t in open_}),
           "unassigned": sum(1 for t in open_ if not t.get("owners")),
           "snapshot": iso(os.path.getmtime(ZOHO_SNAPSHOT))}
    try:
        out["drafts"] = _drafts()
    except Exception as e:
        out["drafts"] = None
        out["draftsError"] = type(e).__name__
    return out


# ---------------------------------------------------------------- main
def safe(fn, *a):
    try:
        return {"ok": True, "data": fn(*a)}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}


def collect():
    rep = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    rep["jobs"] = safe(card_jobs)
    rep["usage"] = safe(card_usage)
    mcp = MCP(HOMELAB_MCP)
    try:
        if not HOMELAB_MCP:
            raise RuntimeError("FRAME_HOMELAB_MCP is not set")
        mcp.start()
        rep["fleet"] = safe(card_fleet, mcp)
    except Exception as e:
        rep["fleet"] = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    if rep["fleet"]["ok"]:
        rep["power"] = safe(card_power, mcp, rep["fleet"]["data"]["hosts"])
    else:
        rep["power"] = {"ok": False, "error": "homelab monitor unreachable"}
    rep["long"] = safe(card_long)
    rep["waiting"] = safe(card_waiting)
    return rep


def main():
    rep = collect()
    if "--dry" in sys.argv:
        print(json.dumps(rep, indent=1))
        return
    req = urllib.request.Request(env("FAMILY_FRAME_URL").rstrip("/") + "/api/agents/push",
                                 data=json.dumps(rep).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Frame-Token": env("FAMILY_FRAME_TOKEN")},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        json.load(resp)
    bad = [k for k in ("jobs", "usage", "fleet", "power", "long", "waiting") if not rep[k]["ok"]]
    log("OK" + (" (errors: %s)" % ", ".join(bad) if bad else ""))
    print("OK", bad or "")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FAILED %s %s" % (type(e).__name__, str(e)[:200]))
        print("FAILED", type(e).__name__, str(e)[:200])
        sys.exit(1)
