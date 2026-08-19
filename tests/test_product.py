import json
import unittest
from pathlib import Path

from n0jcg_noaa_weather_radio.channels import NOAA_CHANNELS
from n0jcg_noaa_weather_radio.fft_scan import FftPoint, MIN_VALID_SNR_DB, score_channels, simulated_spectrum
from n0jcg_noaa_weather_radio.same import SameFilter, alert_matches, parse_same_header
from n0jcg_noaa_weather_radio.server import NOAA_AUDIO_GAIN_DB, NOAA_AUDIO_INPUT_RATE_HZ, NOAA_AUDIO_OUTPUT_RATE_HZ


class ProductTests(unittest.TestCase):
    def test_seven_canonical_channels(self):
        self.assertEqual([c.frequency_hz for c in NOAA_CHANNELS], [162400000,162425000,162450000,162475000,162500000,162525000,162550000])

    def test_fft_selects_strongest_candidate(self):
        winner = score_channels(simulated_spectrum())[0]
        self.assertEqual(winner.channel.number, "WX4")
        self.assertEqual(winner.peak_frequency_hz, 162_475_000 + 2_500)

    def test_noise_floor_is_not_a_valid_weather_candidate(self):
        points = [FftPoint(162_400_000 + index * 625, -13.4) for index in range(256)]
        self.assertLess(score_channels(points)[0].snr_db, MIN_VALID_SNR_DB)

    def test_same_header_filter(self):
        alert = parse_same_header("ZCZC-WXR-TOR-006001+0015-2321800-KXYZ-")
        self.assertIsNotNone(alert)
        self.assertTrue(alert_matches(alert, SameFilter(counties={"006001"}, events={"TOR"})))
        self.assertFalse(alert_matches(alert, SameFilter(counties={"013001"})))
        self.assertTrue(alert_matches(alert, SameFilter(counties={"006001"}, events={"ALL"})))

    def test_product_identity_and_receive_only_ui(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(json.loads((root / "config/noaa-weather-radio.example.json").read_text())["rtl_serial"], "00000162")
        ui = (root / "web/app.js").read_text() + (root / "web/index.html").read_text()
        self.assertNotIn("/api/transmit", ui)
        self.assertIn('id="listen"', ui)
        self.assertIn('async function listen()', ui)
        self.assertIn('/api/audio.pcm', ui)
        self.assertIn('AudioContext', ui)
        self.assertIn('createScriptProcessor', ui)
        self.assertIn('No valid NOAA carrier found; audio is not started.', ui)
        self.assertIn('RESTART REQUIRED', ui)
        self.assertIn('TRIAL PAUSED', ui)
        self.assertIn('formatTrialTime', ui)
        self.assertIn('/assets/N0JCG_Header_Dark_Approved.png', ui)
        self.assertIn('<h1>Weather Radio</h1>', ui)
        self.assertIn('N0JCG Weather Radio', ui)
        self.assertNotIn('N0JCG WEATHER RADIO', ui)
        self.assertIn('/api/trial/restart', ui + (root / 'src/n0jcg_noaa_weather_radio/server.py').read_text())

    def test_audio_profile_matches_validated_noaa_path(self):
        self.assertEqual((NOAA_AUDIO_INPUT_RATE_HZ, NOAA_AUDIO_OUTPUT_RATE_HZ), (240000, 24000))
        self.assertEqual(NOAA_AUDIO_GAIN_DB, 49.6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
