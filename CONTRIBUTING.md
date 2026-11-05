# Contributing

Thanks for helping. Bug reports, ideas and pull requests are welcome. For a larger change, open an issue
first, so we can agree on the approach before you spend time on it.

## Never post personal data

This repository is public, and every commit stays public. Never include tokens, `verdi_state.json`, HAR
files, screenshots of a browser's network tab, Verdi IDs (GUIDs), your Verdi address or tenant, or anyone's
name, not in issues, pull requests, commits, test fixtures or screenshots. Test data and screenshots use
made-up names and places. Report security problems privately: see [SECURITY.md](SECURITY.md).

## What the integration may call

The integration only reads what your own Verdi account can see, and only changes your own status and
planning, when that is switched on. Every request it makes is listed in
[docs/endpoints.md](docs/endpoints.md), and a test keeps that list equal to the API client's allowlist. A
new request needs an issue first; other writes to Verdi are not accepted.

## Development

Python 3.14. Home Assistant's test package, and the frontend that Home Assistant version needs:

```sh
pip install "pytest-homeassistant==2026.11.0" "ruff==0.17.3"
pip install --no-deps "$(python -c "import json, pathlib, homeassistant.components.frontend as f; print(json.loads((pathlib.Path(f.__file__).parent / 'manifest.json').read_text())['requirements'][0])")"
```

Before you open a pull request:

```sh
python -m pytest -q
ruff check . && ruff format --check .
python scripts/check_version.py
python scripts/check_image_metadata.py
```

CI also runs the tests on the oldest supported Home Assistant (2026.4.0, with
`pytest-homeassistant-custom-component==0.13.321`), hassfest, the HACS check and the app build.

## Versions and changelog

A change to the integration raises its version in `custom_components/verdi/manifest.json` and gets an entry
in [CHANGELOG.md](CHANGELOG.md). The Token Relay app has its own version (`verdi_token_relay/config.yaml`
and `VERSION` in its script) and its own `verdi_token_relay/CHANGELOG.md`; it changes only when the app
itself changes. Documentation-only changes need no new version.

## License

Contributions are accepted under the project's license, GPL-3.0-or-later with the additional terms in
[ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md). Please don't change LICENSE, ADDITIONAL_TERMS.md or the
DISCLAIMER files in a pull request.

This project follows a [code of conduct](CODE_OF_CONDUCT.md).
