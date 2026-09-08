# N0JCG NOAA Weather Radio

N0JCG NOAA Weather Radio is a receive-only Raspberry Pi appliance for scanning
the seven US NOAA Weather Radio channels with RTL-SDR serial `00000162`.
It performs a wide FFT survey, selects the strongest valid channel, demodulates
NFM audio, and parses SAME alert headers when the optional decoder dependency is
available. Operator filters, alert history, registration, and deployment are
independent of N0JCG Scanner and N0JCG Air Traffic Center.

## Current release boundary

Version 1.0.0 is the first packaged product release. Simulation mode, FFT scoring,
configuration, registration state, SAME parsing, tests, UI, installer, and
documentation are included. Live RF audio, real antenna coverage, USB
enumeration, and end-to-end SAME decode require validation on the target Pi.
Transmit controls are intentionally absent.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m n0jcg_noaa_weather_radio.server --simulate
```

Open `http://127.0.0.1:8086/`. The default live service uses
`/opt/n0jcg-noaa-weather-radio` and `n0jcg-noaa-weather-radio.service`.

## Product surfaces

- [Operator guide](docs/N0JCG_NOAA_WEATHER_RADIO_USER_GUIDE.md)
- [Release and validation notes](docs/RELEASE_v1.0.0.md)
- [Configuration example](config/noaa-weather-radio.example.json)
- [Deployment installer](deploy/install.sh)

The canonical future GitHub repository is `bakstaaj/N0JCG-NOAA-WEATHER-RADIO`.
