# N0JCG NOAA Weather Radio

## Operator user guide v0.1.3

N0JCG NOAA Weather Radio is a receive-only Raspberry Pi appliance. It uses one
RTL-SDR identified by EEPROM serial `00000162`, surveys the seven NOAA Weather
Radio channels with FFT power measurements, tunes the strongest candidate, and
keeps the operator informed about receiver state and alert filters.

## Safety and operating boundary

This product has no transmit path. It is not an emergency alert replacement;
keep an official weather receiver or other warning source available. Antenna,
geography, terrain, interference, receiver gain, and local NOAA coverage affect
what can be heard. A green application status proves software state, not RF
coverage or the correctness of a warning.

## Hardware

Use a Raspberry Pi with current 64-bit Raspberry Pi OS, stable power, network
access for installation, an RTL-SDR with serial `00000162`, and a suitable
VHF antenna. Disconnect other RTL-SDRs when programming or verifying the serial
identity. USB enumeration is not proof of serial ownership; the application
passes the required serial to its RTL tools and does not use a temporary index.

## Installation

From an MSYS2 UCRT64 shell in this repository:

```bash
./deploy/install.sh --check-only
./deploy/install.sh
```

Open `http://<pi-address>:8086/`. The service is
`n0jcg-noaa-weather-radio.service`, the application root is
`/opt/n0jcg-noaa-weather-radio`, and runtime state is kept under its `runtime/`
directory. Use `systemctl status n0jcg-noaa-weather-radio` and
`journalctl -u n0jcg-noaa-weather-radio` for diagnosis.

## First operation

1. Confirm the page shows RTL-SDR `00000162`.
2. Press **Start**. The application surveys 162.395-162.555 MHz, scores a
   window around every canonical channel, and starts browser audio on the
   strongest valid candidate.
3. Review the candidate cards. Click any card to tune that NOAA channel
   directly and start its audio path.
4. Press **Stop**—the same button changes from Start to Stop—before
   disconnecting the receiver or changing USB hardware.

The SAME alert settings and operator controls are available from the hamburger
menu in the header.

### Browser audio

Pressing **Start** or selecting a candidate card starts the browser audio path
for the tuned channel. The receiver demodulates narrow FM at 48 kHz and the
server provides short 24 kHz mono WAV segments to the browser for scheduled
playback. Use the browser and operating-system volume controls; a connected
audio indicator confirms the software path, not intelligible RF reception.

Simulation mode (`--simulate`) intentionally selects a deterministic test
winner and is useful for UI validation. It is not a live RF test.

## NOAA channel plan

| Channel | Frequency |
|---|---:|
| WX1 | 162.400 MHz |
| WX2 | 162.425 MHz |
| WX3 | 162.450 MHz |
| WX4 | 162.475 MHz |
| WX5 | 162.500 MHz |
| WX6 | 162.525 MHz |
| WX7 | 162.550 MHz |

The FFT score is a candidate-strength measurement. A high peak can be
interference or a local non-weather signal; verify intelligible NOAA audio.

## SAME alerts

Specific Area Message Encoding (SAME) filters are operator-configurable. Enter
county FIPS codes and event codes such as `TOR` or `SVR`, separated by commas.
An empty field accepts all values. The **ALL** event shortcut explicitly
selects every event type. Select **Save / Update SAME settings** after making
changes; the settings are restored after a browser refresh and service restart.

Alert validation requires a live NOAA SAME transmission or a controlled audio
fixture. Record the raw header, UTC receipt time, channel, and whether the
filter matched. Do not treat a parsed test header as an operational warning.

## Registration

The product has its own registration namespace, `n0jcg-noaa-weather-radio`.
Open the hamburger menu to activate the product. Enter the N0JCG license S/N
with prefix `N0JCG-NWR-` and the registered email address, then select
**Activate license**. The application displays the product ID, license prefix,
installation ID, and activation result there. Activation validates a signed,
product-scoped lease for this installation and stores the credentials and lease
under the private runtime license directory. While unregistered, the main
dashboard continues to show the five-minute trial card and timer; both are
removed after successful activation.

## Troubleshooting

- **No device:** check `rtl_test -d 00000162`, USB power, permissions, and that
  no other SDR process owns the device.
- **No candidates:** check antenna connection, gain, local NOAA coverage, and
  `rtl_power` availability. A missing candidate is not proof that the RTL-SDR
  is defective.
- **Wrong winner:** inspect all candidate SNR values, lower gain if saturated,
  and confirm the antenna and RF environment.
- **No SAME alert:** confirm intelligible 1050 Hz alert tone/audio and use a
  live or recorded SAME fixture. Browser status alone cannot prove decoder
  health.
- **Service failure:** run the systemd status and journal commands above, then
  rerun the installer with `--check-only`.

## Support boundary and release evidence

The v0.1.3 release includes software tests, simulation mode, static UI checks,
the compact operator dashboard, direct channel tuning, scheduled browser WAV
audio, and package construction. Hardware-dependent acceptance remains pending until
the specified RTL-SDR is connected on the target Pi and a live FFT scan, NFM
audio, and controlled SAME fixture are recorded.
