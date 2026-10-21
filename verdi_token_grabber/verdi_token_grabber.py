#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Verdi Token Grabber: keeps a Verdi token in Home Assistant, without stored passwords.

Unofficial, not affiliated with Cevi or Verdi, not for operational use. It uses your own
Verdi account and its permissions. Use at your own risk.

How it works
------------
* `login` (on a PC with a screen, once): opens a browser window where YOU sign in to
  Verdi, including MFA. The signed-in browser state is saved to a "storage state" file
  (verdi_state.json). It holds cookies, never your password. Treat it like a password.
* `run` (the Home Assistant app, or a long-running service): starts a fresh headless
  browser from that file whenever the token is close to expiry. Microsoft Entra's
  "stay signed in" cookie then completes the normal web login without interaction.
  The current token is kept in memory and pushed to Home Assistant's
  POST /api/verdi/token every 90 seconds, and again as soon as Home Assistant is
  reachable after an outage. Tokens are never written to disk or printed.

Settings come from environment variables (or /data/options.json inside the app):

    VERDI_URL      https://<zone>.verdi.cloud
    VERDI_TENANT   your tenant name, as in the web login's acr_values (tenant:<name>)
    VERDI_CULTURE  login page language (default nl)
    HA_URL         Home Assistant base URL, e.g. http://homeassistant.local:8123
    HA_TOKEN       long-lived access token of a dedicated Home Assistant admin user
    HA_ENTRY_ID    optional: config entry ID to deliver to (needed with several entries)
    VERDI_STATE    storage state file (default verdi_state.json)

Run only against your own account.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import secrets
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

LOG = logging.getLogger("verdi_token_grabber")

VERSION = "0.5.6"  # scripts/check_version.py keeps this equal to the app and integration

PUSH_INTERVAL = 90  # seconds between re-pushes of the current token
TICK = 10  # main loop resolution; also how fast an HA outage is noticed as over
REFRESH_MARGIN = 300  # run the browser login when less than this is left
RETRY_LOGIN = 900  # after a failed headless login, wait this long before trying again
GATEWAY_ERRORS = (502, 503, 504)  # proxy answers while Home Assistant is (re)starting
CLIENT_ID = "verdi-web"
SCOPE = "openid profile verdi-api verdi-communications"


@dataclass
class Settings:
    verdi_url: str
    tenant: str
    culture: str
    ha_url: str | None
    ha_token: str | None
    entry_id: str | None
    state: Path


def load_settings(addon: bool) -> Settings:
    env = dict(os.environ)
    if addon:
        options = json.loads(Path("/data/options.json").read_text(encoding="utf-8"))
        env.update(
            VERDI_URL=options.get("verdi_url", ""),
            VERDI_TENANT=options.get("tenant", ""),
            VERDI_CULTURE=options.get("culture") or "nl",
            HA_URL="http://supervisor/core",
            HA_TOKEN=os.environ.get("SUPERVISOR_TOKEN", ""),
            HA_ENTRY_ID=options.get("entry_id") or "",
            VERDI_STATE="/data/verdi_state.json",
        )
    url = env.get("VERDI_URL", "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        sys.exit("Set VERDI_URL to the https address of your Verdi zone.")
    tenant = env.get("VERDI_TENANT", "").strip()
    if not tenant:
        sys.exit("Set VERDI_TENANT to your Verdi tenant name.")
    return Settings(
        verdi_url=f"{parsed.scheme}://{parsed.netloc}",
        tenant=tenant,
        culture=env.get("VERDI_CULTURE", "").strip() or "nl",
        ha_url=(env.get("HA_URL") or "").strip().rstrip("/") or None,
        ha_token=(env.get("HA_TOKEN") or "").strip() or None,
        entry_id=(env.get("HA_ENTRY_ID") or "").strip() or None,
        state=Path(env.get("VERDI_STATE") or "verdi_state.json").expanduser().resolve(),
    )


def authorize_url(s: Settings) -> str:
    """The same authorize request the Verdi web app sends."""
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": f"{s.verdi_url}/callback",
        "response_type": "id_token token",
        "scope": SCOPE,
        "state": secrets.token_hex(16),
        "nonce": secrets.token_hex(16),
        "enableSingleExternalProviderRedirect": "true",
        "culture": s.culture,
        "acr_values": f"tenant:{s.tenant}",
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{s.verdi_url}/auth/connect/authorize?{query}"


def token_from_url(url: str, callback: str) -> str | None:
    if not url.startswith(callback):
        return None
    fragment = urllib.parse.parse_qs(urllib.parse.urlsplit(url).fragment)
    return (fragment.get("access_token") or [None])[0]


def expiry(token: str | None) -> datetime | None:
    try:
        payload = token.split(".")[1]  # type: ignore[union-attr]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return datetime.fromtimestamp(int(claims["exp"]), UTC)
    except (AttributeError, IndexError, KeyError, ValueError, TypeError):
        return None


def seconds_left(token: str | None) -> float:
    exp = expiry(token)
    return (exp - datetime.now(UTC)).total_seconds() if exp else -1


def save_state(context, path: Path) -> None:
    """Write the storage state atomically, readable by the owner only."""
    state = context.storage_state()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".verdi_state.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def seed_marker(state: Path) -> Path:
    """Records when the login state was created by an interactive login (MFA)."""
    return state.with_name(state.name + ".seeded")


def mark_seeded(state: Path) -> None:
    seed_marker(state).write_text(datetime.now(UTC).isoformat() + "\n", encoding="utf-8")


def state_age_days(state: Path) -> float | None:
    try:
        seeded = datetime.fromisoformat(seed_marker(state).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return (datetime.now(UTC) - seeded).total_seconds() / 86400


def where(url: str) -> str:
    """Host and path only: queries and fragments can hold state, codes or tokens."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.netloc}{parts.path}" or "(no page)"


def browser_login(s: Settings, headless: bool, timeout_s: int) -> str | None:
    """Run the web login once. Returns the access token, or None if it needs a human."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    callback = f"{s.verdi_url}/callback"
    seen: list[str] = []
    with sync_playwright() as pw:
        # The full Chromium build; the slimmer headless shell is treated differently by
        # some sign-in pages.
        browser = pw.chromium.launch(headless=headless, channel="chromium")
        try:
            context = browser.new_context(storage_state=str(s.state) if s.state.exists() else None)
            page = context.new_page()
            # The web app may rewrite the URL after loading, so record every navigation.
            page.on("framenavigated", lambda frame: seen.append(frame.url))
            with suppress(PlaywrightError):
                page.goto(authorize_url(s), wait_until="domcontentloaded", timeout=30000)
            deadline = time.monotonic() + timeout_s
            token = None
            while time.monotonic() < deadline:
                token = next((t for u in [*seen, page.url] if (t := token_from_url(u, callback))), None)
                if token:
                    break
                page.wait_for_timeout(500)
            if token:
                save_state(context, s.state)
            else:
                with suppress(PlaywrightError):
                    LOG.warning("Login stopped at %s (page title: %r)", where(page.url), page.title())
            return token
        finally:
            browser.close()


def push(s: Settings, token: str) -> bool | None:
    """Deliver the token to Home Assistant. True: accepted. False: refused. None: unreachable."""
    body = {"token": token}
    if s.entry_id:
        body["entry_id"] = s.entry_id
    request = urllib.request.Request(
        f"{s.ha_url}/api/verdi/token",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {s.ha_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            return True
    except urllib.error.HTTPError as err:
        if err.code in GATEWAY_ERRORS:  # inside HA OS: the Supervisor proxy while Core restarts
            return None
        try:
            result = json.loads(err.read() or b"{}").get("result", "")
        except ValueError:
            result = ""
        hints = {
            "no_matching_entry": "no Verdi entry matches this account; set HA_ENTRY_ID",
            "expired": "the token expired before it was delivered",
            "forbidden": "the Home Assistant user must be an administrator",
        }
        if err.code == 404:
            LOG.error("Home Assistant has no /api/verdi/token yet; is the Verdi integration installed?")
            return None
        LOG.error("Home Assistant refused the token (HTTP %s %s)", err.code, hints.get(result, result))
        return False
    except (urllib.error.URLError, OSError):
        return None


def handle_stop_signal() -> None:
    """Exit cleanly on SIGTERM. As process 1 in a container the default action does not apply,
    so without this the Supervisor waits 10 seconds and then kills the app (exit code 137)."""

    def stop(_signum, _frame) -> None:
        LOG.info("Stopping")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)


def run(s: Settings, addon: bool = False) -> None:
    if not (s.ha_url and s.ha_token):
        sys.exit("Set HA_URL and HA_TOKEN.")
    if not s.state.exists():
        sys.exit(f"No login state at {s.state}. Run the one-time 'login' step on a PC first.")
    handle_stop_signal()
    LOG.info(
        "Verdi Token Grabber %s (%s), pushing to Home Assistant every %s s",
        VERSION,
        "app" if addon else "standalone",
        PUSH_INTERVAL,
    )
    if state_age_days(s.state) is None:
        LOG.info("Unknown when the login state was created (before version 0.5.4); counting from now")
        mark_seeded(s.state)
    token: str | None = None
    last_push = 0.0
    reachable = True
    delivered = False
    next_login = 0.0
    while True:
        now = time.monotonic()
        if seconds_left(token) < REFRESH_MARGIN and now >= next_login:
            fresh = browser_login(s, headless=True, timeout_s=45)
            took = time.monotonic() - now
            if fresh:
                token = fresh
                age = state_age_days(s.state)
                LOG.info(
                    "New Verdi token, valid until %s (login took %.0f s%s)",
                    expiry(token),
                    took,
                    f", login state seeded {age:.1f} days ago" if age is not None else "",
                )
                last_push = 0.0
                delivered = False
            else:
                next_login = now + RETRY_LOGIN
                retry_at = datetime.now().astimezone() + timedelta(seconds=RETRY_LOGIN)
                LOG.error(
                    "The login needs interaction. Next attempt at %s. If this keeps happening, redo "
                    "the one-time login on a PC with this script ('login'), copy the new "
                    "verdi_state.json here and restart.",
                    retry_at.strftime("%H:%M"),
                )
        if token and seconds_left(token) > 60 and (not reachable or now - last_push >= PUSH_INTERVAL):
            result = push(s, token)
            if result is None:
                if reachable:
                    LOG.warning("Home Assistant is not reachable; retrying every %s s", TICK)
                reachable = False
                delivered = False
            else:
                if not reachable:
                    LOG.info("Home Assistant is reachable again")
                reachable = True
                last_push = now
                if result and not delivered:
                    LOG.info("Token delivered to Home Assistant")
                    delivered = True
        time.sleep(TICK)


def login(s: Settings, push_after: bool) -> None:
    token = browser_login(s, headless=False, timeout_s=300)
    if not token:
        sys.exit("No token appeared within 5 minutes. Did the login finish?")
    mark_seeded(s.state)
    print(f"Signed in. Login state saved to {s.state}. Token valid until {expiry(token)}.")
    if push_after and s.ha_url and s.ha_token:
        print("Delivered to Home Assistant." if push(s, token) else "Delivery to Home Assistant failed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("command", choices=("login", "run"))
    parser.add_argument("--addon", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--push", action="store_true", help="login: also deliver the token to HA")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings(args.addon)
    if args.command == "login":
        login(settings, args.push)
    else:
        run(settings, args.addon)


if __name__ == "__main__":
    main()
