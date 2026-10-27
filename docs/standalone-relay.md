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

## 3a. Docker

```sh
mkdir -p verdi-data && cp verdi_state.json verdi-data/ && chmod 600 verdi-data/verdi_state.json
docker run -d --name verdi-token-relay --restart=always \
  -e VERDI_URL=https://yourzone.verdi.cloud \
  -e VERDI_TENANT=YourTenant \
  -e HA_URL=http://homeassistant.local:8123 \
  -e HA_TOKEN=<long-lived token of the dedicated user> \
  -v "$PWD/verdi-data:/data" \
  ghcr.io/jertech/verdi-ha-token-relay:0.9.0
```

Prefer an `--env-file` with permissions `600` over putting `HA_TOKEN` on the command line.

## 3b. systemd

```ini
# /etc/systemd/system/verdi-token-relay.service
[Unit]
Description=Verdi Token Relay (unofficial)
After=network-online.target
Wants=network-online.target

[Service]
User=verdi
EnvironmentFile=/etc/verdi-token-relay.env   # VERDI_URL, VERDI_TENANT, HA_URL, HA_TOKEN, VERDI_STATE; chmod 600
ExecStart=/opt/verdi/venv/bin/python /opt/verdi/verdi_token_relay.py run
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

The venv needs `pip install playwright==1.64.0 && playwright install --with-deps chromium`.

## Several Verdi entries

With more than one Verdi entry in Home Assistant, set `HA_ENTRY_ID` to the config entry ID the
relay delivers to (visible in the address bar when you open the entry under
**Settings > Devices & services**). With a single entry this is not needed.
