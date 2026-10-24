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
CONF_SCAN_INTERVAL = "scan_interval"  # seconds: the station's normal tick
CONF_INTERVENTION_INTERVAL = "intervention_interval"  # seconds: the tick during an intervention
CONF_WATCHED_VEHICLES = "watched_vehicles"  # vehicle ids that count for triggers; empty = all
CONF_SHOW_NAMES = "show_names"
# Your own data, one switch each.
CONF_MY_AVAILABILITY = "my_availability"
CONF_PAGED = "paged"  # stored for the paging feature; not used yet
CONF_PRE_ALERT = "pre_alert"
CONF_GARRISON = "garrison"
CONF_MY_EVENTS = "my_events"
CONF_STATISTICS = "statistics"
# Safety intervals: the longest time between two fetches of a lookup.
CONF_READINESS_SAFETY = "readiness_safety"  # minutes
CONF_ROSTER_SAFETY = "roster_safety"  # minutes; roster and roster calendar
CONF_TEAMS_SAFETY = "teams_safety"  # hours
CONF_AVAILABILITY_SAFETY = "availability_safety"  # minutes
CONF_ALERTS_SAFETY = "alerts_safety"  # minutes; pre-alert and garrison
CONF_EVENTS_INTERVAL = "events_interval"  # minutes
CONF_STATISTICS_INTERVAL = "statistics_interval"  # hours

# Config flow only, never stored.
CONF_VERDI_URL = "verdi_url"
CONF_TOKEN = "token"
CONF_ACCEPT = "accept_disclaimer"

CONF_NON_PAGEABLE = "non_pageable"  # availability names that mean "not pageable"; unset = word list
NON_PAGEABLE_WORDS = (
    "niet beschikbaar", "onbeschikbaar", "non disponible", "indisponible",
    "not available", "unavailable",
)

# Removed in config entry version 2.
LEGACY_TOKEN_KEYS = ("token", "token_file")

# Removed in config entry version 3: your person GUID now comes from security/users/authorize.
LEGACY_PERSON_ID = "person_id"

# Removed in config entry version 4: one switch per kind of your own data, and triggers.
LEGACY_PERSONAL_DATA = "personal_data"
LEGACY_PERSONAL_INTERVAL = "personal_interval"
# Version 1 entries were migrated with this floor for the station interval.
LEGACY_MIN_SCAN_INTERVAL = 60

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
MIN_SCAN_INTERVAL = 30
DEFAULT_SCAN_INTERVAL = 60

# Your own data: which kinds are on by default.
FEATURES = {
    CONF_MY_AVAILABILITY: True,
    CONF_PAGED: True,
    CONF_PRE_ALERT: False,
    CONF_GARRISON: False,
    CONF_MY_EVENTS: True,
    CONF_STATISTICS: True,
}

# Interval options: (default, minimum, maximum, seconds per unit).
INTERVALS = {
    CONF_SCAN_INTERVAL: (DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL, 3600, 1),
    CONF_INTERVENTION_INTERVAL: (30, 15, 3600, 1),
    CONF_READINESS_SAFETY: (15, 5, 1440, 60),
    CONF_ROSTER_SAFETY: (30, 10, 1440, 60),
    CONF_TEAMS_SAFETY: (6, 1, 168, 3600),
    CONF_AVAILABILITY_SAFETY: (30, 5, 1440, 60),
    CONF_ALERTS_SAFETY: (60, 10, 1440, 60),
    CONF_EVENTS_INTERVAL: (60, 10, 1440, 60),
    CONF_STATISTICS_INTERVAL: (24, 1, 168, 3600),
    # The fast personal lookups' poll interval; no longer an option.
    LEGACY_PERSONAL_INTERVAL: (60, 10, 3600, 1),
}
# Defaults before version 4, moved to the new defaults on migration when unchanged.
OLD_DEFAULTS = {CONF_SCAN_INTERVAL: 120, CONF_EVENTS_INTERVAL: 10, CONF_STATISTICS_INTERVAL: 6}
# Your own data: poll a failed lookup again this soon; refresh statistics daily at this local
# time, and this many seconds after a vehicle of the station starts or ends an intervention.
PERSONAL_RETRY_SECONDS = 300
STATISTICS_DAILY_AT = (0, 5)
STATISTICS_AFTER_INTERVENTION = 120

# When to poll what (schedule.py, signals.py). Randomness spreads the load on Verdi.
JITTER = 0.1  # paces and safety intervals vary ±10 % per run
BOUNDARY_DELAY = (30, 120)  # seconds after a team rotation or roster boundary
END_DELAY = (5, 30)  # seconds after your availability or a pre-alert ends
STARTUP_DELAY = (60, 600)  # seconds before your events and statistics are first fetched
TRIGGER_DELAY = (0, 60)  # extra seconds on triggered event and statistics fetches
CALL_GAP = (0.2, 1.0)  # seconds between the calls of one run
STATISTICS_MAX_DELAY = 600  # a burst of triggers delays statistics at most this long
DAILY_OFFSET_MAX = 2700  # per-entry seconds after 00:05 for the daily statistics refresh
DAILY_JITTER = 900  # plus up to this many seconds per day: between 00:05 and 01:05
MIN_WAKE = 5  # seconds; a coordinator never wakes sooner
IDLE_WAKE = 3600  # seconds; wake this often when nothing is due at all

# Per entry (guard.py): calls per minute over all coordinators, the first backoff for callers
# without a tick, backoff cap, and how long 401/403 answers are tolerated without a success
# before asking to sign in again.
CALL_CAP = 30
BACKOFF_START = 60
BACKOFF_MAX = 300
REJECTED_WINDOW = 120
CALENDAR_CACHE = 300  # seconds a roster calendar range is served from memory

# After Home Assistant starts, wait this long for the token relay to push a token
# before asking the user to re-authenticate.
TOKEN_GRACE_SECONDS = 600
# Tokens with less time left than this are treated as expired.
TOKEN_MIN_REMAINING = 60

TOKEN_VIEW_URL = "/api/verdi/token"
TOKEN_VIEW_MAX_BYTES = 16 * 1024

ISSUE_MISSING_CONFIG = "missing_config"
