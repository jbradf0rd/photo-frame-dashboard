#!/usr/bin/env python3
"""Download the two Adhan recordings and make the alert chime.

The Adhan files are not stored in this repo. They come from the archive.org item
"adhanclock-qurancube" (Quran Cube Adhan Clock Adhans), which states no license, so each
person downloads them from the source. Every download is checked against a pinned SHA-256.

Needs ffmpeg on PATH. Writes web/public/audio/adhan-fajr.mp3, adhan.mp3 and chime.mp3.

    python scripts/fetch-audio.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ITEM = "https://archive.org/download/adhanclock-qurancube/"
FILES = {
    # output name: (path inside the archive.org item, SHA-256 of the original file)
    "adhan-fajr.mp3": ("Adhan Clock - Quran Cube - Final/Fajr 3 - Makkah QC.mp3",
                       "c286fa6da567b4622983707fc47bb2645ecdf5b4819462af84d193abcd8aef58"),
    "adhan.mp3": ("Adhan Clock - Quran Cube - Final/Adhan 13 - Hussain shahat.mp3",
                  "7131a6ee53d41bbbb01ed95bd67e1747e891b0a7d4c07627bd8c35ff01570a47"),
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "public", "audio")
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, (path, sha) in FILES.items():
            url = ITEM + urllib.parse.quote(path)
            raw = os.path.join(tmp, name)
            print("download", path)
            urllib.request.urlretrieve(url, raw)
            got = hashlib.sha256(open(raw, "rb").read()).hexdigest()
            if got != sha:
                sys.exit("SHA-256 mismatch for %s: got %s, expected %s" % (path, got, sha))
            # Same loudness for both files, mono, 44.1 kHz, 128 kbit/s.
            ffmpeg("-i", raw, "-af", LOUDNORM, "-ac", "1", "-ar", "44100", "-b:a", "128k",
                   os.path.join(OUT, name))
    # Two-note chime for the full-screen alert, made from sine tones.
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=880:duration=0.35",
           "-f", "lavfi", "-i", "sine=frequency=660:duration=0.6",
           "-filter_complex", "[0][1]concat=n=2:v=0:a=1,afade=t=out:st=0.6:d=0.35,volume=0.6",
           "-ac", "1", "-ar", "44100", "-b:a", "96k", os.path.join(OUT, "chime.mp3"))
    print("OK", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
