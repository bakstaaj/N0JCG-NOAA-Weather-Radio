from __future__ import annotations

import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import struct
import time
from urllib.parse import urlparse

from . import PRODUCT_NAME, REQUIRED_RTL_SERIAL
from .channels import NOAA_CHANNELS, channel_for_frequency
from .fft_scan import FftPoint, MIN_VALID_SNR_DB, score_channels, simulated_spectrum
from .registration import activate as activate_license, registration_status
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
NOAA_AUDIO_CHUNK_SAMPLES = 12_000
NOAA_AUDIO_CHUNK_BYTES = NOAA_AUDIO_CHUNK_SAMPLES * 2
TRIAL_DURATION_SECONDS = 300


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
        self.same_filter_path = RUNTIME / "same-filter.json"
        try:
            saved_filter = json.loads(self.same_filter_path.read_text(encoding="utf-8"))
            self.same_filter = SameFilter(set(saved_filter.get("counties", [])), set(saved_filter.get("events", [])), str(saved_filter.get("min_priority", "all")))
        except (FileNotFoundError, ValueError, TypeError):
            pass
        self.config = {"rtl_serial": REQUIRED_RTL_SERIAL, "same": {"enabled": True}}
        self.audio_process: subprocess.Popen[bytes] | None = None
        self.trial_started_at = time.monotonic()
        self.trial_paused = False
        if not registration_status(RUNTIME / "registration.json").get("registered"):
            self.trial_timer = threading.Timer(TRIAL_DURATION_SECONDS, self._expire_trial)
            self.trial_timer.daemon = True
            self.trial_timer.start()
        else:
            self.trial_timer = None

    def _expire_trial(self) -> None:
        with self.lock:
            if registration_status(RUNTIME / "registration.json").get("registered"):
                return
            self.trial_paused = True
            self.running = False
            self._stop_audio()

    def _restart_trial_locked(self) -> None:
        if registration_status(RUNTIME / "registration.json").get("registered"):
            return
        if self.trial_timer is not None:
            self.trial_timer.cancel()
        self.trial_started_at = time.monotonic()
        self.trial_paused = False
        self.trial_timer = threading.Timer(TRIAL_DURATION_SECONDS, self._expire_trial)
        self.trial_timer.daemon = True
        self.trial_timer.start()

    def restart_trial(self) -> dict[str, object]:
        with self.lock:
            self._restart_trial_locked()
            return self.snapshot()
    def registration(self) -> dict[str, object]:
        status = registration_status(RUNTIME / "registration.json")
        if status.get("registered"):
            return status
        remaining = max(0, int(TRIAL_DURATION_SECONDS - (time.monotonic() - self.trial_started_at)))
        if self.trial_paused or remaining == 0:
            self.trial_paused = True
            status.update({"mode": "trial_paused", "trial_paused": True, "trial_remaining_seconds": 0, "restart_required": True})
        else:
            status.update({"trial_paused": False, "trial_remaining_seconds": remaining, "restart_required": False})
        return status

    def trial_available(self) -> bool:
        status = self.registration()
        return bool(status.get("registered") or not status.get("trial_paused"))

    def scan(self) -> dict[str, object]:
        with self.lock:
            if not self.trial_available():
                self._restart_trial_locked()
            # Release a manual/listen receiver before asking rtl_power to claim
            # the same RTL-SDR.  A failed scan must not leave stale audio alive.
            self._stop_audio()
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
                self._stop_audio()
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
        # Use the same one-shot file-output form as Air Traffic Center.  The
        # streaming -e form can be terminated by the subprocess timeout before
        # rtl_power returns success, leaving the scanner with no usable rows.
        RUNTIME.mkdir(parents=True, exist_ok=True)
        csv_path = RUNTIME / "noaa-spectrum.csv"
        csv_path.unlink(missing_ok=True)
        command = [
            "rtl_power", "-d", REQUIRED_RTL_SERIAL,
            "-f", "162395000:162555000:1000", "-i", "1", "-1",
            "-g", "40", str(csv_path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=18, check=False)
        except (OSError, subprocess.SubprocessError):
            return []
        if result.returncode != 0 or not csv_path.is_file():
            return []
        points: list[FftPoint] = []
        for fields in csv.reader(csv_path.read_text(encoding="utf-8", errors="replace").splitlines()):
            if len(fields) < 7: continue
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
        same_filter = {"counties": sorted(self.same_filter.counties), "events": sorted(self.same_filter.events), "min_priority": self.same_filter.min_priority}
        return {"ok": True, "product": PRODUCT_NAME, "simulate": self.simulate, "rtl_serial": REQUIRED_RTL_SERIAL, "running": self.running, "audio_profile": {"input_sample_rate_hz": NOAA_AUDIO_INPUT_RATE_HZ, "sample_rate_hz": NOAA_AUDIO_OUTPUT_RATE_HZ, "gain_db": NOAA_AUDIO_GAIN_DB, "offset_tuning": True, "dc_block": True, "deemphasis": True}, "registration": self.registration(), "same_filter": same_filter, "tuned": tuned, "candidates": [{"channel": c.channel.__dict__, "peak_frequency_hz": c.peak_frequency_hz, "peak_dbfs": c.peak_dbfs, "noise_floor_dbfs": c.noise_floor_dbfs, "snr_db": c.snr_db} for c in self.candidates], "alerts": self.alerts[-20:]}

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
        if path == "/api/registration": self._json(STATE.registration()); return
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
        if path == "/api/audio.chunk.wav":
            process = STATE.audio_process
            if not process or not process.stdout or not STATE.running:
                self._json({"ok": False, "error": "audio_not_running"}, 409); return
            chunk = process.stdout.read(NOAA_AUDIO_CHUNK_BYTES)
            if len(chunk) != NOAA_AUDIO_CHUNK_BYTES:
                self._json({"ok": False, "error": "audio_chunk_unavailable"}, 503); return
            data_size = len(chunk)
            header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, NOAA_AUDIO_OUTPUT_RATE_HZ, NOAA_AUDIO_OUTPUT_RATE_HZ * 2, 2, 16) + b"data" + struct.pack("<I", data_size)
            body = header + chunk
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
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
        if path == "/api/trial/restart": self._json(STATE.restart_trial()); return
        if path == "/api/tune":
            if not STATE.trial_available(): STATE.restart_trial()
            STATE.tuned = channel_for_frequency(int(payload.get("frequency_hz", 162_550_000))); STATE.tune_frequency_hz = STATE.tuned.frequency_hz; STATE.running = True
            if not STATE.simulate: STATE._start_audio()
            self._json(STATE.snapshot()); return
        if path == "/api/same/filter":
            STATE.same_filter = SameFilter(set(payload.get("counties", [])), set(payload.get("events", [])), str(payload.get("min_priority", "all"))); RUNTIME.mkdir(parents=True, exist_ok=True); STATE.same_filter_path.write_text(json.dumps({"counties": sorted(STATE.same_filter.counties), "events": sorted(STATE.same_filter.events), "min_priority": STATE.same_filter.min_priority}, indent=2) + "\n", encoding="utf-8"); self._json(STATE.snapshot()); return
        if path == "/api/same/test": self._json({"ok": True, "matched": STATE.ingest_same(str(payload.get("header", ""))) }); return
        if path == "/api/registration/activate":
            try:
                state_path = RUNTIME / "registration.json"
                self._json(activate_license(state_path, str(payload.get("license_serial", "")), str(payload.get("email", ""))))
            except Exception as error:
                self._json({"ok": False, "error": str(error), "registration": STATE.registration()}, 400)
            return
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
