# SPDX-License-Identifier: GPL-3.0-or-later
FROM python:3.13-slim-bookworm

# Playwright is pinned; Dependabot proposes updates, and the image is rebuilt for
# Chromium security releases.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

COPY verdi_token_grabber.py run.sh /app/
RUN chmod +x /app/run.sh

LABEL org.opencontainers.image.source="https://github.com/jertech/verdi-ha" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.description="Verdi Token Grabber (unofficial)"

CMD ["/app/run.sh"]
