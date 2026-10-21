#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu

if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
    # Home Assistant app: take a dropped-in login state once, then remove the seed copy,
    # so other apps that can read app configuration folders no longer see it.
    if [ -f /config/verdi_state.json ]; then
        echo "Taking the login state from the app configuration folder"
        install -m 600 /config/verdi_state.json /data/verdi_state.json
        rm -f /config/verdi_state.json
    fi
    exec python3 /app/verdi_token_grabber.py run --addon
fi

# Standalone container: settings from environment variables, state under /data.
export VERDI_STATE="${VERDI_STATE:-/data/verdi_state.json}"
exec python3 /app/verdi_token_grabber.py run
