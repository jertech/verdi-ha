# SPDX-License-Identifier: GPL-3.0-or-later
"""The token grabber builds the web app's own authorize request and never prints tokens."""

import importlib.util
import json
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
