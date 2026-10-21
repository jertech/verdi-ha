# SPDX-License-Identifier: GPL-3.0-or-later
"""The token grabber builds the web app's own authorize request and never prints tokens."""

import importlib.util
import io
import json
import logging
import sys
import urllib.parse
from pathlib import Path

import pytest

from tests.conftest import make_token

SCRIPT = Path(__file__).resolve().parent.parent / "verdi_token_grabber" / "verdi_token_grabber.py"
spec = importlib.util.spec_from_file_location("verdi_token_grabber", SCRIPT)
grabber = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = grabber
spec.loader.exec_module(grabber)


@pytest.fixture
def settings(tmp_path):
    return grabber.Settings(
        verdi_url="https://zone.verdi.example",
        tenant="TENANT_X",
        culture="nl",
        ha_url="http://ha.example:8123",
        ha_token="ha-token",
        entry_id=None,
        state=tmp_path / "verdi_state.json",
    )


def test_authorize_url(settings):
    url = urllib.parse.urlsplit(grabber.authorize_url(settings))
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://zone.verdi.example/auth/connect/authorize"
    q = dict(urllib.parse.parse_qsl(url.query))
    assert q["client_id"] == "verdi-web"
    assert q["redirect_uri"] == "https://zone.verdi.example/callback"
    assert q["response_type"] == "id_token token"
    assert q["scope"] == "openid profile verdi-api verdi-communications"
    assert q["acr_values"] == "tenant:TENANT_X"
    assert q["enableSingleExternalProviderRedirect"] == "true"
    assert q["culture"] == "nl"
    assert len(q["state"]) == 32 and len(q["nonce"]) == 32
    assert "%20" in url.query and "+" not in url.query  # encoded like the web app


def test_token_from_callback_only():
    token = make_token()
    cb = "https://zone.verdi.example/callback"
    assert grabber.token_from_url(f"{cb}#id_token=x&access_token={token}&expires_in=3600", cb) == token
    assert grabber.token_from_url(f"https://evil.example/callback#access_token={token}", cb) is None


def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VERDI_URL", "https://zone.verdi.example/home")
    monkeypatch.setenv("VERDI_TENANT", "T")
    monkeypatch.setenv("VERDI_STATE", str(tmp_path / "s.json"))
    s = grabber.load_settings(addon=False)
    assert s.verdi_url == "https://zone.verdi.example"
    monkeypatch.setenv("VERDI_URL", "http://insecure.example")
    with pytest.raises(SystemExit):
        grabber.load_settings(addon=False)


def test_push_never_logs_token(settings, monkeypatch, caplog):
    token = make_token()
    sent = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data)
        return Resp()

    monkeypatch.setattr(grabber.urllib.request, "urlopen", fake_urlopen)
    assert grabber.push(settings, token) is True
    assert sent["url"] == "http://ha.example:8123/api/verdi/token"
    assert sent["body"] == {"token": token}
    assert token not in caplog.text


def test_push_unreachable(settings, monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(grabber.urllib.request, "urlopen", boom)
    assert grabber.push(settings, make_token()) is None


def http_error(code):
    def fail(*a, **k):
        raise grabber.urllib.error.HTTPError("http://x", code, "error", None, io.BytesIO(b""))

    return fail


@pytest.mark.parametrize("code", [502, 503, 504])
def test_push_gateway_error_is_unreachable(settings, monkeypatch, caplog, code):
    # Inside HA OS the Supervisor proxy answers 502 while Core restarts.
    monkeypatch.setattr(grabber.urllib.request, "urlopen", http_error(code))
    with caplog.at_level(logging.INFO):
        assert grabber.push(settings, make_token()) is None
    assert "refused" not in caplog.text


def test_push_refused(settings, monkeypatch, caplog):
    monkeypatch.setattr(grabber.urllib.request, "urlopen", http_error(401))
    assert grabber.push(settings, make_token()) is False
    assert "refused the token (HTTP 401" in caplog.text


def test_state_age(settings):
    assert grabber.state_age_days(settings.state) is None
    grabber.mark_seeded(settings.state)
    assert 0 <= grabber.state_age_days(settings.state) < 0.01


def run_loop(settings, monkeypatch, logins, pushes, ticks):
    """Run the main loop for a number of ticks, with fake logins, pushes and clock."""
    settings.state.write_text("{}")
    clock = iter(range(0, 100000, 100))
    monkeypatch.setattr(grabber.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(grabber, "browser_login", lambda *a, **k: logins.pop(0) if logins else None)
    monkeypatch.setattr(grabber, "push", lambda s, token: pushes.pop(0) if pushes else True)
    left = iter(range(ticks))

    def sleep(_seconds):
        if next(left, None) is None:
            raise SystemExit

    monkeypatch.setattr(grabber.time, "sleep", sleep)
    with pytest.raises(SystemExit):
        grabber.run(settings, addon=True)


def test_run_logs_state_changes_once(settings, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    token = make_token()
    run_loop(settings, monkeypatch, logins=[token], pushes=[True, True, None, None, True], ticks=6)
    text = caplog.text
    assert f"Verdi Token Grabber {grabber.VERSION} (app)" in text
    assert "counting from now" in text
    assert "New Verdi token, valid until" in text
    assert "login took" in text
    assert "login state seeded 0.0 days ago" in text
    # Delivered once per token, and again after Home Assistant was unreachable.
    assert text.count("Token delivered to Home Assistant") == 2
    assert text.count("Home Assistant is not reachable") == 1
    assert token not in text


def test_failed_login_says_when_it_retries(settings, monkeypatch, caplog):
    run_loop(settings, monkeypatch, logins=[], pushes=[], ticks=1)
    assert "The login needs interaction. Next attempt at " in caplog.text
