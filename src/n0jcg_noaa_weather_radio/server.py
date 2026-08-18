from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import struct
from urllib.parse import urlparse

from . import PRODUCT_NAME, REQUIRED_RTL_SERIAL
from .channels import NOAA_CHANNELS, channel_for_frequency
from .fft_scan import FftPoint, MIN_VALID_SNR_DB, score_channels, simulated_spectrum
from .registration import registration_status
from .same import SameFilter, alert_matches, parse_same_header


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "web"
RUNTIME = ROOT / "runtime"

# Match the validated NOAA path used by N0JCG Air Traffic Center.  The RTL
# input rate gives the FM discriminator room around the channel; the lower
# output rate is the operator audio stream.  Offset tuning lets rtl_fm correct
# the tuner center internally instead of retuning to an FFT noise-bin peak.
NOAA_AUDIO_INPUT_RATE_HZ = 240_000
NOAA_AUDIO_OUTPUT_RATE_HZ = 24_000
NOAA_AUDIO_GAIN_DB = 49.6


class RadioState:
    def __init__(self, simulate: bool = False) -> None:
        self.simulate = simulate
        self.lock = threading.Lock()
        self.points: list[FftPoint] = []
        self.candidates = []
        self.tuned = None
        self.tune_frequency_hz: int | None = None
        self.running = False
        self.alerts: list[dict[str, object]] = []
        self.same_filter = SameFilter()
        self.config = {"rtl_serial": REQUIRED_RTL_SERIAL, "same": {"enabled": True}}
        self.audio_process: subprocess.Popen[bytes] | None = None

    def scan(self) -> dict[str, object]:
        with self.lock:
            self.points = simulated_spectrum() if self.simulate else self._rtl_power_spectrum()
            self.candidates = score_channels(self.points)
            if self.candidates and self.candidates[0].snr_db >= MIN_VALID_SNR_DB:
                self.tuned = self.candidates[0].channel
                self.tune_frequency_hz = self.candidates[0].peak_frequency_hz
                self.running = True
                if not self.simulate:
                    self._start_audio()
            else:
                self.candidates = []
                self.tuned = None
                self.tune_frequency_hz = None
                self.running = False
            return self.snapshot()

    def _start_audio(self) -> None:
        self._stop_audio()
        # Tune the canonical NOAA channel and let rtl_fm's offset tuner absorb
        # the measured FFT-bin offset.  Directly tuning the peak bin was
        # producing a narrow/static-prone discriminator path.
        command = [
            "rtl_fm", "-d", REQUIRED_RTL_SERIAL,
            "-f", str(self.tuned.frequency_hz), "-M", "fm",
            "-s", str(NOAA_AUDIO_INPUT_RATE_HZ),
            "-r", str(NOAA_AUDIO_OUTPUT_RATE_HZ),
            "-g", str(NOAA_AUDIO_GAIN_DB), "-l", "0", "-p", "0",
            "-E", "offset", "-E", "dc", "-E", "deemp",
        ]
        try:
            self.audio_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self.audio_process = None

    def _stop_audio(self) -> None:
        if self.audio_process and self.audio_process.poll() is None:
            self.audio_process.terminate()
            try:
                self.audio_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.audio_process.kill()
        self.audio_process = None

    def stop(self) -> None:
        with self.lock:
            self.running = False
            self._stop_audio()

    def _rtl_power_spectrum(self) -> list[FftPoint]:
        command = ["rtl_power", "-f", "162.395M:162.555M:1k", "-i", "1", "-e", "1s", "-g", "40", "-d", REQUIRED_RTL_SERIAL]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=True)
        except (OSError, subprocess.SubprocessError):
            return []
        points: list[FftPoint] = []
        for line in result.stdout.splitlines():
            fields = line.split(",")
            if len(fields) < 7:
                continue
            try:
                start, step = float(fields[2]), float(fields[4])
                powers = [float(item) for item in fields[6:]]
            except ValueError:
                continue
            scale = 1 if start > 1_000_000 else 1_000_000
            points.extend(FftPoint(int((start + index * step) * scale), power) for index, power in enumerate(powers))
        return points

    def snapshot(self) -> dict[str, object]:
        tuned = self.tuned.__dict__.copy() if self.tuned else None
        if tuned and self.tune_frequency_hz:
            tuned["tuned_frequency_hz"] = self.tune_frequency_hz
            tuned["offset_hz"] = self.tune_frequency_hz - self.tuned.frequency_hz
        return {"ok": True, "product": PRODUCT_NAME, "simulate": self.simulate, "rtl_serial": REQUIRED_RTL_SERIAL, "running": self.running, "audio_profile": {"input_sample_rate_hz": NOAA_AUDIO_INPUT_RATE_HZ, "sample_rate_hz": NOAA_AUDIO_OUTPUT_RATE_HZ, "gain_db": NOAA_AUDIO_GAIN_DB, "offset_tuning": True, "dc_block": True, "deemphasis": True}, "tuned": tuned, "candidates": [{"channel": c.channel.__dict__, "peak_frequency_hz": c.peak_frequency_hz, "noise_floor_dbfs": c.noise_floor_dbfs, "snr_db": c.snr_db} for c in self.candidates], "alerts": self.alerts[-20:]}

    def ingest_same(self, text: str) -> bool:
        alert = parse_same_header(text)
        if not alert or not alert_matches(alert, self.same_filter):
            return False
        with self.lock:
            self.alerts.append(alert.__dict__)
        return True


STATE = RadioState()


class Handler(BaseHTTPRequestHandler):
    def _json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value, default=lambda obj: obj.__dict__).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status": self._json(STATE.snapshot()); return
        if path == "/api/registration": self._json(registration_status(RUNTIME / "registration.json")); return
        if path == "/api/channels": self._json({"channels": [channel.__dict__ for channel in NOAA_CHANNELS]}); return
        if path == "/api/audio.wav":
            process = STATE.audio_process
            if not process or not process.stdout:
                self._json({"ok": False, "error": "audio_not_running"}, 409); return
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
            header = b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, NOAA_AUDIO_OUTPUT_RATE_HZ, NOAA_AUDIO_OUTPUT_RATE_HZ * 2, 2, 16) + b"data" + struct.pack("<I", 0xFFFFFFFF)
            self._chunk(header)
            while STATE.running and process.poll() is None:
                chunk = process.stdout.read(4096)
                if not chunk: break
                self._chunk(chunk)
            return
        if path == "/api/audio.pcm":
            process = STATE.audio_process
            if not process or not process.stdout:
                self._json({"ok": False, "error": "audio_not_running"}, 409); return
            self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
            while STATE.running and process.poll() is None:
                chunk = process.stdout.read(4096)
                if not chunk: break
                self._chunk(chunk)
            return
        if path == "/": self._serve("index.html"); return
        if path.startswith("/"):
            self._serve(path[1:]); return
        self._json({"ok": False, "error": "not_found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        try: payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError: self._json({"ok": False, "error": "invalid_json"}, 400); return
        if path == "/api/scan": self._json(STATE.scan()); return
        if path == "/api/stop": STATE.stop(); self._json(STATE.snapshot()); return
        if path == "/api/tune":
            STATE.tuned = channel_for_frequency(int(payload.get("frequency_hz", 162_550_000))); STATE.tune_frequency_hz = STATE.tuned.frequency_hz; STATE.running = True
            if not STATE.simulate: STATE._start_audio()
            self._json(STATE.snapshot()); return
        if path == "/api/same/filter":
            STATE.same_filter = SameFilter(set(payload.get("counties", [])), set(payload.get("events", [])), str(payload.get("min_priority", "all"))); self._json({"ok": True}); return
        if path == "/api/same/test": self._json({"ok": True, "matched": STATE.ingest_same(str(payload.get("header", ""))) }); return
        if path == "/api/registration/activate":
            token = str(payload.get("license_token", "")).strip()
            if not token: self._json({"ok": False, "error": "license_token_required"}, 400); return
            RUNTIME.mkdir(parents=True, exist_ok=True); state_path = RUNTIME / "registration.json"; saved = registration_status(state_path); saved.update({"license_token": token, "registered": True, "mode": "registered"}); state_path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8"); self._json(saved); return
        self._json({"ok": False, "error": "not_found"}, 404)

    def _serve(self, relative: str) -> None:
        target = (STATIC / relative).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file(): self._json({"ok": False, "error": "not_found"}, 404); return
        body = target.read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _chunk(self, body: bytes) -> None:
        try:
            self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n"); self.wfile.flush()
        except BrokenPipeError:
            STATE.stop()

    def log_message(self, *_args: object) -> None: pass


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--host", default="0.0.0.0"); parser.add_argument("--port", type=int, default=8086); parser.add_argument("--simulate", action="store_true"); args = parser.parse_args()
    global STATE; STATE = RadioState(simulate=args.simulate)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__": main()
