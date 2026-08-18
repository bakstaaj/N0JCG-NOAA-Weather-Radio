from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Iterable

from .channels import NOAA_CHANNELS, NoaaChannel

MIN_VALID_SNR_DB = 6.0


@dataclass(frozen=True)
class FftPoint:
    frequency_hz: int
    power_dbfs: float


@dataclass(frozen=True)
class ScanCandidate:
    channel: NoaaChannel
    peak_dbfs: float
    noise_floor_dbfs: float
    snr_db: float


def score_channels(points: Iterable[FftPoint], half_width_hz: int = 8_000) -> list[ScanCandidate]:
    points = tuple(points)
    if not points:
        return []
    floor = sorted(point.power_dbfs for point in points)[max(0, len(points) // 10)]
    scored: list[ScanCandidate] = []
    for channel in NOAA_CHANNELS:
        window = [p.power_dbfs for p in points if abs(p.frequency_hz - channel.frequency_hz) <= half_width_hz]
        if window:
            peak = max(window)
            scored.append(ScanCandidate(channel, peak, floor, peak - floor))
    return sorted(scored, key=lambda item: (item.snr_db, item.peak_dbfs), reverse=True)


def simulated_spectrum() -> list[FftPoint]:
    """Deterministic spectrum for UI and CI tests; WX4 is the winner."""
    points: list[FftPoint] = []
    for channel in NOAA_CHANNELS:
        peak = -31.0 if channel.number == "WX4" else -63.0
        for offset in (-7500, -2500, 2500, 7500):
            points.append(FftPoint(channel.frequency_hz + offset, peak if offset == 2500 else peak - 8))
    return points
