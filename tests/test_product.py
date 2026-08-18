import json
import unittest
from pathlib import Path

from n0jcg_noaa_weather_radio.channels import NOAA_CHANNELS
from n0jcg_noaa_weather_radio.fft_scan import FftPoint, score_channels, simulated_spectrum
from n0jcg_noaa_weather_radio.same import SameFilter, alert_matches, parse_same_header


class ProductTests(unittest.TestCase):
    def test_seven_canonical_channels(self):
        self.assertEqual([c.frequency_hz for c in NOAA_CHANNELS], [162400000,162425000,162450000,162475000,162500000,162525000,162550000])

    def test_fft_selects_strongest_candidate(self):
        self.assertEqual(score_channels(simulated_spectrum())[0].channel.number, "WX4")

    def test_same_header_filter(self):
        alert = parse_same_header("ZCZC-WXR-TOR-006001+0015-2321800-KXYZ-")
        self.assertIsNotNone(alert)
        self.assertTrue(alert_matches(alert, SameFilter(counties={"006001"}, events={"TOR"})))
        self.assertFalse(alert_matches(alert, SameFilter(counties={"013001"})))

    def test_product_identity_and_receive_only_ui(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(json.loads((root / "config/noaa-weather-radio.example.json").read_text())["rtl_serial"], "00000162")
        ui = (root / "web/app.js").read_text() + (root / "web/index.html").read_text()
        self.assertNotIn("/api/transmit", ui)


if __name__ == "__main__":
    unittest.main(verbosity=2)
