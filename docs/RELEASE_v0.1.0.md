# N0JCG NOAA Weather Radio v0.1.0

## Included

- Standalone product and registration namespace.
- RTL-SDR serial lock for `00000162`.
- Seven-channel NOAA FFT candidate scoring.
- Simulation mode with deterministic strongest-candidate selection.
- SAME header parser, county/event filters, and alert history API.
- Receive-only web dashboard, systemd unit, check-only installer, and release packager.
- Editable Markdown operator guide.

## Validation

Run `python3 -m unittest discover -s tests -v` and `./deploy/install.sh --check-only`.
Live RTL-SDR and SAME validation is intentionally hardware-gated.
