"""Post to the family photo frame (the family-frame server).

  python frame_post.py alert "Dinner is ready"     full-screen popup until someone taps Got it
  python frame_post.py message "Dinner at 6"       line on the Today page (last 5 kept)
  python frame_post.py clear                        clear the message board
  python frame_post.py dismiss                      clear the current alert from here

Reads FAMILY_FRAME_URL and FAMILY_FRAME_TOKEN from the environment or a .env file beside this script. Prints OK or the error.
"""
import json
import os
import sys
import urllib.request

ENV = os.environ.get("FAMILY_FRAME_ENV", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def env(key):
    if os.environ.get(key):
        return os.environ[key]
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("missing %s in %s" % (key, ENV))


def post(path, body):
    req = urllib.request.Request(env("FAMILY_FRAME_URL").rstrip("/") + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Frame-Token": env("FAMILY_FRAME_TOKEN")}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("alert", "message", "clear", "dismiss"):
        raise SystemExit(__doc__)
    kind, text = sys.argv[1], " ".join(sys.argv[2:]).strip()
    if kind in ("alert", "message") and not text:
        raise SystemExit("no text given")
    path = {"alert": "/api/alert", "message": "/api/message", "clear": "/api/message/clear", "dismiss": "/api/alert/dismiss"}[kind]
    try:
        r = post(path, {"text": text, "from": "Dad"})
    except Exception as e:
        print("FAILED: %s %s" % (type(e).__name__, str(e)[:200]))
        sys.exit(1)
    print("OK" if r.get("ok") else "FAILED: %s" % r)


if __name__ == "__main__":
    main()
