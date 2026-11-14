# Final Test Report

## Initial environment-limited run

Command: `python -m pytest -q`

The initial run reported **162 passed, 2 setup errors, 0 skipped**, 144.76 seconds. Both errors were `tmp_path` setup failures because Windows denied access to the host temp root. Pytest also emitted two cache path warnings. No assertion failures were reported.

The prior Phase 6 report attributes three `RuntimeWarning: Mean of empty slice` warnings to a one-row sample interval calculation. `intelligence/features.py` now checks available intervals before taking a median. The initial run reported no such runtime warning.

## Delivery verification

Command: `python -m pytest -q -p no:cacheprovider --basetemp '.pytest-audit-tmp\\final'`

Final full suite after the SQLite handle-close fix: **166 passed, 0 failed, 0 skipped** in 80.99 seconds. No pytest warnings were reported. The workspace-local base temp directory avoided the host permission and pytest-cache issues.

After adding transparent gzip compression to stored JSON payloads, the focused persistence suite was rerun: **2 passed, 0 failed** in 4.99 seconds. The demo then completed again and its two sessions occupied a 3.4 MB local SQLite database.
