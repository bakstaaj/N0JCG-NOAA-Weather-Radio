# N0JCG NOAA Weather Radio v0.1.2

## Release summary

This release adds product-scoped N0JCG registration to the operator menu while
retaining the five-minute trial experience until activation.

## Included

- Product ID `n0jcg-noaa-weather-radio` and license prefix `N0JCG-NWR-`.
- Shared N0JCG signed-license client with product, email, and installation
  binding.
- License S/N and registered-email activation form in the hamburger menu.
- Trial card and countdown while unregistered; the card and timer disappear
  after successful activation.
- Seven-channel NOAA FFT survey, direct tuning, and browser WAV audio.

## Validation

- Seven Python unit tests passing.
- JavaScript syntax check passing.
- Installer check-only validation passing.
- Registration metadata tests confirm the NOAA product ID and license prefix.

## Deployment identity

- Service: `n0jcg-noaa-weather-radio.service`
- Application root: `/opt/n0jcg-noaa-weather-radio`
- Port: `8086`
- Receiver: RTL-SDR EEPROM serial `00000162`

## Boundaries

Activation requires a valid signed license from the N0JCG licensing service.
The product remains receive-only; registration does not add transmit controls.
