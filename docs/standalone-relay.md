# Running the Token Relay without Home Assistant OS

Use this when you run Home Assistant Container or Core. The relay must run **continuously**
(a service or a container with a restart policy), not as a scheduled job: it keeps the token in
memory, re-pushes it every 90 seconds, pushes again right after Home Assistant restarts, and only
runs the browser login shortly before the token expires.

## 1. A dedicated Home Assistant user

1. **Settings > People > Users > Add user**, for example `verdi-relay`. It must be an
   **administrator**, because the token endpoint only accepts administrators. Do not reuse your
   own account.
2. Log in as that user once, open its profile, **Security > Long-lived access tokens > Create token**.
3. Keep this token secret. To revoke the relay's access, delete the token or the user; your
   own login is unaffected.

## 2. One-time login

Do step 3 of the [README](../README.md#3-one-time-login-on-a-pc) to create `verdi_state.json`.

Besides the settings below, the relay reads two optional ones: `VERDI_CULTURE` (the login page's language,
`nl` by default) and `HA_ENTRY_ID` (see [Several Verdi entries](#several-verdi-entries)).

## 3a. Docker

```sh
mkdir -p verdi-data && cp verdi_state.json* verdi-data/ && chmod 600 verdi-data/verdi_state.json*
docker run -d --name verdi-token-relay --restart=always \
  -e VERDI_URL=https://yourzone.verdi.cloud \
  -e VERDI_TENANT=YourTenant \
  -e HA_URL=http://homeassistant.local:8123 \
  -e HA_TOKEN=<long-lived token of the dedicated user> \
  -v "$PWD/verdi-data:/data" \
  ghcr.io/jertech/verdi-ha-token-relay:1.0.0
```

`verdi_state.json*` also copies `verdi_state.json.seeded`, which the relay uses to log how old the login is.
Prefer an `--env-file` with permissions `600` over putting `HA_TOKEN` on the command line.

## 3b. systemd

The relay runs as its own system user, `verdi`. It needs Python 3.11 or later. Run these from the folder of this
repository, with `verdi_state.json` from step 2 next to it:

```sh
sudo useradd --system --create-home --shell /usr/sbin/nologin verdi
sudo mkdir -p /opt/verdi
sudo cp verdi_token_relay/verdi_token_relay.py /opt/verdi/
sudo python3 -m venv /opt/verdi/venv
sudo /opt/verdi/venv/bin/pip install playwright==1.64.1
sudo PLAYWRIGHT_BROWSERS_PATH=/opt/verdi/browsers /opt/verdi/venv/bin/playwright install --with-deps chromium
sudo install -d -o verdi -g verdi -m 700 /var/lib/verdi-token-relay
sudo install -o verdi -g verdi -m 600 verdi_state.json* /var/lib/verdi-token-relay/
```

`PLAYWRIGHT_BROWSERS_PATH` puts the browser where the `verdi` user finds it; without it, Playwright installs it in
root's home folder and the relay can't start it.

Put the settings in `/etc/verdi-token-relay.env`, readable only by root (`chmod 600`):

```ini
VERDI_URL=https://yourzone.verdi.cloud
VERDI_TENANT=YourTenant
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<long-lived token of the dedicated user>
VERDI_STATE=/var/lib/verdi-token-relay/verdi_state.json
PLAYWRIGHT_BROWSERS_PATH=/opt/verdi/browsers
```

Add `VERDI_CULTURE` and `HA_ENTRY_ID` if you need them.

```ini
# /etc/systemd/system/verdi-token-relay.service
[Unit]
Description=Verdi Token Relay (unofficial)
After=network-online.target
Wants=network-online.target

[Service]
User=verdi
EnvironmentFile=/etc/verdi-token-relay.env
ExecStart=/opt/verdi/venv/bin/python /opt/verdi/verdi_token_relay.py run
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then `sudo systemctl daemon-reload && sudo systemctl enable --now verdi-token-relay`, and follow the log with
`journalctl -u verdi-token-relay -f`.

## Several Verdi entries

With more than one Verdi entry in Home Assistant, set `HA_ENTRY_ID` to the config entry ID the
relay delivers to. To find it, open **Developer tools > Template** in Home Assistant and enter
`{{ config_entry_id('sensor.verdi_token_expires') }}`, using the **Token expires** sensor of the entry the relay
should feed (its entity ID may end in `_2` and so on for the other entries). With a single entry this is not
needed.
