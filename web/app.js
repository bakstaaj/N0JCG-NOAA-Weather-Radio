const $ = (id) => document.getElementById(id);
const fmt = (hz) => `${(hz / 1e6).toFixed(3)} MHz`;
let audioAbort = null;
let audioContext = null;
let audioNode = null;
let audioQueue = [];
let audioQueueOffset = 0;
let trialRemainingSeconds = null;
let trialPaused = false;
function renderRegistration(registration) {
  if (!registration) return;
  trialRemainingSeconds = registration.trial_remaining_seconds ?? null;
  trialPaused = Boolean(registration.trial_paused);
  $("registration").textContent = trialPaused ? "TRIAL PAUSED" : registration.registered ? "REGISTERED" : `TRIAL ${formatTrialTime(trialRemainingSeconds)}`;
  $("installation").textContent = trialPaused ? "RESTART REQUIRED" : registration.installation_id;
}
function formatTrialTime(seconds) {
  if (seconds == null) return "";
  const value = Math.max(0, Number(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}
function render(state) {
  const tuned = state.tuned;
  $("summary").textContent = state.simulate ? "Simulation mode - no live RF claim" : "Receive-only live mode";
  $("serial").textContent = state.rtl_serial;
  $("tuned").textContent = tuned ? tuned.number : "Not tuned";
  $("frequency").textContent = tuned ? fmt(tuned.frequency_hz) : "-";
  const winner = state.candidates?.[0];
  $("snr").textContent = winner ? `${winner.snr_db.toFixed(1)} dB SNR` : "-";
  $("scanState").textContent = state.running ? "Audio path selected" : "Stopped";
  $("channels").innerHTML = (state.candidates || []).map((item) => `<div class="channel ${winner && item.channel.number === winner.channel.number ? "winner" : ""}"><strong>${item.channel.number}</strong><span>${item.channel.label}</span><small>${item.peak_dbfs.toFixed(1)} dBFS / ${item.snr_db.toFixed(1)} dB SNR</small></div>`).join("") || "<p>No spectrum candidates yet.</p>";
  $("alerts").innerHTML = (state.alerts || []).map((a) => `<div class="alert"><strong>${a.event}</strong> · ${a.locations.join(", ")}<br><small>${a.received_at}</small></div>`).join("") || "No matching alerts.";
}
async function api(path, options) { const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options}); const data = await response.json(); $("log").textContent = JSON.stringify(data, null, 2); if (!response.ok) throw new Error(data.error); return data; }
async function refresh() {
  try {
    const state = await api("/api/status");
    render(state);
    renderRegistration(state.registration);
    $("status").textContent = "READY";
    $("status").className = "pill ok";
  } catch (error) {
    $("status").textContent = "OFFLINE";
    $("status").className = "pill warn";
    $("log").textContent = error.message;
  }
}
async function listen() {
  let state = await api("/api/status");
  if (!state.running) state = await api("/api/scan", {method:"POST", body:"{}"});
  render(state);
  if (state.simulate) { $("log").textContent = "Simulation mode has no live audio stream."; return; }
  if (!state.running || !state.tuned) {
    stopPcmAudio();
    $("audioStatus").hidden = false;
    $("audioStatus").textContent = "No valid NOAA carrier found; audio is not started.";
    return;
  }
  await startPcmAudio();
}
async function startPcmAudio() {
  stopPcmAudio();
  audioAbort = new AbortController();
  audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 24000});
  await audioContext.resume();
  audioQueue = [];
  audioQueueOffset = 0;
  audioNode = audioContext.createScriptProcessor(4096, 0, 1);
  audioNode.onaudioprocess = (event) => {
    const output = event.outputBuffer.getChannelData(0);
    output.fill(0);
    let written = 0;
    while (written < output.length && audioQueue.length) {
      const source = audioQueue[0];
      const available = source.length - audioQueueOffset;
      const count = Math.min(available, output.length - written);
      output.set(source.subarray(audioQueueOffset, audioQueueOffset + count), written);
      written += count;
      audioQueueOffset += count;
      if (audioQueueOffset >= source.length) { audioQueue.shift(); audioQueueOffset = 0; }
    }
  };
  audioNode.connect(audioContext.destination);
  $("audioStatus").hidden = false;
  $("audioStatus").textContent = "Live PCM audio connected - use system/browser volume.";
  const response = await fetch("/api/audio.pcm?listen=" + Date.now(), {signal: audioAbort.signal});
  if (!response.ok || !response.body) throw new Error("live PCM audio stream unavailable");
  const reader = response.body.getReader();
  let carry = new Uint8Array(0);
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      const bytes = new Uint8Array(carry.length + part.value.length);
      bytes.set(carry); bytes.set(part.value, carry.length); carry = bytes;
      const usable = bytes.length - (bytes.length % 2);
      if (!usable) continue;
      const samples = new Float32Array(usable / 2);
      const view = new DataView(bytes.buffer, bytes.byteOffset, usable);
      for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
      carry = bytes.slice(usable);
      audioQueue.push(samples);
    }
  } catch (error) { if (error.name !== "AbortError") throw error; }
}
function stopPcmAudio() {
  if (audioAbort) audioAbort.abort(); audioAbort = null;
  if (audioNode) { audioNode.disconnect(); audioNode = null; }
  if (audioContext) { audioContext.close(); audioContext = null; }
  audioQueue = []; audioQueueOffset = 0;
  $("audioStatus").hidden = true;
}
$("scan").onclick = async () => {
  const state = await api("/api/scan", {method:"POST", body:"{}"});
  render(state);
  if (state.simulate) return;
  if (state.running && state.tuned) await startPcmAudio();
  else {
    stopPcmAudio();
    $("audioStatus").hidden = false;
    $("audioStatus").textContent = "No valid NOAA carrier found; audio is not started.";
  }
};
$("listen").onclick = () => listen().catch((error) => { $("log").textContent = error.message; });
$("stop").onclick = async () => { stopPcmAudio(); const state = await api("/api/stop", {method:"POST", body:"{}"}); render(state); };
$("saveFilter").onclick = async () => { await api("/api/same/filter", {method:"POST", body:JSON.stringify({counties:$("counties").value.split(",").map(v=>v.trim()).filter(Boolean), events:$("events").value.split(",").map(v=>v.trim()).filter(Boolean)})}); };
$("testAlert").onclick = async () => { await api("/api/same/test", {method:"POST", body:JSON.stringify({header:"ZCZC-WXR-TOR-006001+0015-2321800-KXYZ-"})}); await refresh(); };
setInterval(() => {
  if (trialRemainingSeconds != null && !trialPaused) {
    trialRemainingSeconds = Math.max(0, trialRemainingSeconds - 1);
    $("registration").textContent = trialRemainingSeconds ? `TRIAL ${formatTrialTime(trialRemainingSeconds)}` : "TRIAL PAUSED";
    if (!trialRemainingSeconds) $("installation").textContent = "RESTART REQUIRED";
  }
}, 1000);
refresh(); setInterval(refresh, 5000);
