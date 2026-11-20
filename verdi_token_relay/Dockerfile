# SPDX-License-Identifier: GPL-3.0-or-later
FROM python:3.15-slim-bookworm

# Playwright is pinned; Dependabot proposes updates, and a new app
# version publishes a new image.
COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY verdi_token_relay.py run.sh /app/
RUN chmod +x /app/run.sh

LABEL org.opencontainers.image.source="https://github.com/jertech/verdi-ha" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.description="Verdi Token Relay (unofficial)"

CMD ["/app/run.sh"]
