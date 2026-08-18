#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="/opt/n0jcg-noaa-weather-radio"
CHECK_ONLY=0
[[ "${1:-}" == "--check-only" ]] && CHECK_ONLY=1
if [[ ! -d "$(dirname "$0")/.." ]]; then echo "source root missing" >&2; exit 1; fi
echo "N0JCG NOAA Weather Radio installer"
echo "Required receiver serial: 00000162"
if [[ "$CHECK_ONLY" -eq 1 ]]; then
  command -v python3 >/dev/null
  command -v rtl_power >/dev/null || echo "WARN: rtl_power not installed; live FFT scan will be unavailable"
  echo "PASS: check-only preflight"
  exit 0
fi
sudo install -d -o pi -g pi "$APP_ROOT" "$APP_ROOT/runtime"
sudo cp -a "$(dirname "$0")/.."/. "$APP_ROOT"/
sudo chown -R pi:pi "$APP_ROOT"
sudo install -m 0644 "$(dirname "$0")/../systemd/n0jcg-noaa-weather-radio.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now n0jcg-noaa-weather-radio.service
echo "Installed at http://$(hostname -I | awk '{print $1}'):8086/"
