from dataclasses import dataclass


@dataclass(frozen=True)
class NoaaChannel:
    number: str
    frequency_hz: int
    label: str


NOAA_CHANNELS = (
    NoaaChannel("WX1", 162_400_000, "162.400 MHz"),
    NoaaChannel("WX2", 162_425_000, "162.425 MHz"),
    NoaaChannel("WX3", 162_450_000, "162.450 MHz"),
    NoaaChannel("WX4", 162_475_000, "162.475 MHz"),
    NoaaChannel("WX5", 162_500_000, "162.500 MHz"),
    NoaaChannel("WX6", 162_525_000, "162.525 MHz"),
    NoaaChannel("WX7", 162_550_000, "162.550 MHz"),
)


def channel_for_frequency(frequency_hz: int) -> NoaaChannel:
    return min(NOAA_CHANNELS, key=lambda channel: abs(channel.frequency_hz - frequency_hz))
