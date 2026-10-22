# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jertech and contributors
# Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
"""Constants for the Verdi integration."""

DOMAIN = "verdi"

# entry.data
CONF_BASE_URL = "base_url"  # <verdi address>/verdi-core/api/v1
CONF_STATION_ID = "station_id"
CONF_TEAM_GROUP_ID = "team_group_id"
CONF_VEHICLE_TRAIN_IDS = "vehicle_train_ids"
CONF_CREW_FUNCTION_IDS = "crew_function_ids"
CONF_AVAILABILITY_IDS = "availability_ids"
CONF_FUNCTION_CALENDAR_ID = "function_calendar_id"
CONF_ACCOUNT_SUB = "account_sub"

# entry.options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PERSON_ID = "person_id"
CONF_SHOW_NAMES = "show_names"
CONF_PERSONAL_DATA = "personal_data"
CONF_PERSONAL_INTERVAL = "personal_interval"  # seconds
CONF_EVENTS_INTERVAL = "events_interval"  # minutes
CONF_STATISTICS_INTERVAL = "statistics_interval"  # hours

# Config flow only, never stored.
CONF_VERDI_URL = "verdi_url"
CONF_TOKEN = "token"
CONF_ACCEPT = "accept_disclaimer"

# Removed in config entry version 2.
LEGACY_TOKEN_KEYS = ("token", "token_file")

API_PATH = "/verdi-core/api/v1"

REQUIRED_DATA = (
    CONF_BASE_URL,
    CONF_STATION_ID,
    CONF_TEAM_GROUP_ID,
    CONF_VEHICLE_TRAIN_IDS,
    CONF_CREW_FUNCTION_IDS,
    CONF_AVAILABILITY_IDS,
)

# This is an emergency-service platform: keep the load low.
MIN_SCAN_INTERVAL = 60
DEFAULT_SCAN_INTERVAL = 120
DEFAULT_PERSONAL_DATA = True

# Interval options: (default, minimum, maximum, seconds per unit).
INTERVALS = {
    CONF_SCAN_INTERVAL: (DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL, 3600, 1),
    CONF_PERSONAL_INTERVAL: (60, 10, 3600, 1),
    CONF_EVENTS_INTERVAL: (10, 1, 1440, 60),
    CONF_STATISTICS_INTERVAL: (6, 1, 168, 3600),
}
# Your own data: poll a failed lookup again this soon; refresh statistics daily at this local
# time, and this many seconds after a vehicle of the station starts or ends an intervention.
PERSONAL_RETRY_SECONDS = 300
STATISTICS_DAILY_AT = (0, 5)
STATISTICS_AFTER_INTERVENTION = 120

# After Home Assistant starts, wait this long for the token relay to push a token
# before asking the user to re-authenticate.
TOKEN_GRACE_SECONDS = 600
# Tokens with less time left than this are treated as expired.
TOKEN_MIN_REMAINING = 60

TOKEN_VIEW_URL = "/api/verdi/token"
TOKEN_VIEW_MAX_BYTES = 16 * 1024

ISSUE_MISSING_CONFIG = "missing_config"
