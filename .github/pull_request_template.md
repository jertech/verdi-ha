## What and why

<!-- What does this change, and why? Link the issue if there is one. -->

## Checks

- [ ] No personal data anywhere: no tokens, Verdi IDs, addresses, tenant names or people's names (also not in fixtures or screenshots).
- [ ] Tests added or updated, and `python -m pytest -q` passes.
- [ ] `ruff check . && ruff format --check .` pass.
- [ ] `node --test tests/js/verdi_panel.test.mjs tests/js/verdi_settings.test.mjs` passes.
- [ ] Version and CHANGELOG updated, if the integration or the app changed.
- [ ] Docs updated, if behaviour or options changed.
