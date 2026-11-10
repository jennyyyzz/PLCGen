# -*- coding: utf-8 -*-
"""One-click public launcher: local service + cloudflared quick tunnel.

Starts two processes and wires them together:

  1. codesys_service/server.py   (local FastAPI service, 127.0.0.1)
  2. cloudflared tunnel          (free quick tunnel, no account, no config)

Then prints a PUBLIC URL like https://xxxx-xxxx.trycloudflare.com and writes
it to out/public_url.txt. Share that URL with the team — they only need a
browser or httpx, nothing installed locally.

Usage:
    python codesys_service/serve_public.py
    python codesys_service/serve_public.py --port 8000
    python codesys_service/serve_public.py --cloudflared C:/path/to/cloudflared.exe

cloudflared lookup order:
    --cloudflared arg  >  CLOUDFLARED env var  >  next to this script /
    script's bin/ / parent's bin/  >  ~/Downloads/cloudflared(-windows-amd64).exe  >  PATH

Notes:
    * The public URL is random and changes on every restart — re-share it
      after restarting. For a fixed URL you'd need a (free) Cloudflare
      account + named tunnel; not required for this course.
    * The host machine must stay awake while the team uses the service.
    * No firewall changes needed: cloudflared makes outbound connections only.
    * Ctrl+C stops both processes.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def log(msg: str):
    print(f"[serve_public] {msg}", flush=True)


def find_cloudflared(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("CLOUDFLARED"):
        candidates.append(Path(os.environ["CLOUDFLARED"]))
    # any cloudflared*.exe / cloudflared* dropped next to the script or in bin/
    for base in (HERE, HERE / "bin", HERE.parent / "bin", HERE.parent):
        if base.is_dir():
            candidates += sorted(base.glob("cloudflared*.exe"))
            candidates += sorted(base.glob("cloudflared*"))
            candidates += [base / "cloudflared", base / "cloudflared.exe"]
    candidates += [
        Path.home() / "Downloads" / "cloudflared-windows-amd64.exe",
        Path.home() / "Downloads" / "cloudflared.exe",
        Path.home() / "Desktop" / "cloudflared-windows-amd64.exe",
        Path.home() / "Desktop" / "cloudflared.exe",
    ]
    which = shutil.which("cloudflared")
    if which:
        candidates.append(Path(which))
    for c in candidates:
        if c.is_file() and c.stat().st_size > 1_000_000:
            return c.resolve()
    searched = "\n  ".join(str(c) for c in candidates)
    sys.exit(
        "cloudflared not found (or file too small to be the real binary).\n"
        "Download it from:\n"
        "  https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-windows-amd64.exe\n"
        "then either pass --cloudflared <path>, set CLOUDFLARED=<path>, or drop "
        "cloudflared.exe next to this script.\nSearched:\n  " + searched
    )


def wait_health(url: str, timeout_s: float, tag: str) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1.0)
    log(f"WARNING: {tag} did not answer /health within {timeout_s:.0f}s "
        f"({url})")
    return False


def main():
    ap = argparse.ArgumentParser(description="local service + public quick tunnel")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--cloudflared", default=None, help="path to cloudflared(.exe)")
    args = ap.parse_args()

    cf = find_cloudflared(args.cloudflared)
    log(f"cloudflared : {cf}")

    # 1) local service
    log("starting local service ...")
    server = subprocess.Popen(
        [PY, str(HERE / "server.py"), "--host", "127.0.0.1",
         "--port", str(args.port)],
        cwd=str(HERE))
    local = f"http://127.0.0.1:{args.port}"
    wait_health(local, 60, "local service")

    # 2) quick tunnel
    log("starting cloudflared quick tunnel ...")
    tunnel = subprocess.Popen(
        [str(cf), "tunnel", "--url", local, "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)

    public_url = None
    deadline = time.time() + 90
    while time.time() < deadline:
        line = tunnel.stdout.readline() if tunnel.stdout else ""
        if line:
            m = URL_RE.search(line)
            if m:
                public_url = m.group(0)
                break
        if tunnel.poll() is not None:
            break
        time.sleep(0.2)

    if not public_url:
        server.terminate()
        tunnel.terminate()
        sys.exit("could not get a public URL from cloudflared within 90s — "
                 "check the cloudflared output above / your network.")

    # 3) verify end-to-end through the public URL
    #    (a freshly created quick tunnel needs ~1 min to warm up at the edge,
    #    so allow a generous timeout and retry instead of failing early)
    log("verifying public URL (first-time edge warm-up can take ~1 min) ...")
    wait_health(public_url, 150, "public URL")

    url_file = HERE / "out" / "public_url.txt"
    url_file.parent.mkdir(parents=True, exist_ok=True)
    url_file.write_text(public_url + "\n", encoding="utf-8")

    print("\n" + "=" * 62)
    print(f"  LOCAL  : {local}          (this machine only)")
    print(f"  PUBLIC : {public_url}   (share this with the team)")
    print(f"  DOCS   : {public_url}/docs")
    print(f"  URL also written to: {url_file}")
    print("=" * 62)
    print("Press Ctrl+C to stop both processes.")
    print("NOTE: the public URL changes on every restart; re-share it.\n",
          flush=True)

    # 4) babysit: if either process dies, stop the other
    try:
        while True:
            if server.poll() is not None:
                log("local service exited; stopping tunnel")
                break
            if tunnel.poll() is not None:
                log("cloudflared exited; stopping local service "
                    "(URL is gone anyway)")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        log("Ctrl+C received")
    finally:
        for p in (server, tunnel):
            if p.poll() is None:
                p.terminate()
        for p in (server, tunnel):
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        log("both processes stopped")


if __name__ == "__main__":
    main()
