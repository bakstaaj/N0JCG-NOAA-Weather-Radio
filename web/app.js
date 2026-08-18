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
let sameLocations = [];
const sameEventCodes = [["TOR", "Tornado Warning"], ["SVR", "Severe Thunderstorm Warning"], ["FFW", "Flash Flood Warning"], ["FLW", "Flood Warning"], ["HWW", "High Wind Warning"], ["EVI", "Evacuation Immediate"], ["RWT", "Required Weekly Test"]];
const escapeHtml = (value) => String(value).replace(/[&<>\"']/g, (character) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;"}[character]));
function addSameValue(id, value) { const input = $(id); const values = input.value.split(",").map((item) => item.trim()).filter(Boolean); if (!values.includes(value)) values.push(value); input.value = values.join(","); input.focus(); }
function renderSameLocations(query = "") { const normalized = query.trim().toLowerCase(); const matches = sameLocations.filter((item) => !normalized || `${item.name} ${item.state} ${item.code}`.toLowerCase().includes(normalized)).slice(0, 30); $("sameLookupCount").textContent = normalized ? `${matches.length}${matches.length === 30 ? "+" : ""} matches` : `${sameLocations.length} counties`; $("sameLocationResults").innerHTML = matches.length ? matches.map((item) => `<button type="button" class="same-result" data-same-code="${item.code}" title="Add ${escapeHtml(item.name)}, ${item.state}"><span><strong>${escapeHtml(item.name)}</strong><small>${item.state} · SAME ${item.code}</small></span><span class="same-add">Add</span></button>`).join("") : "<p class=\"hint\">No county matches. Try a county name, state abbreviation, or six-digit code.</p>"; $("sameLocationResults").querySelectorAll("[data-same-code]").forEach((button) => button.addEventListener("click", () => { addSameValue("counties", button.dataset.sameCode); button.classList.add("added"); button.querySelector(".same-add").textContent = "Added"; })); }
async function loadSameLocations() { try { const response = await fetch("/data/same-codes.json", {cache:"no-store"}); if (!response.ok) throw new Error("lookup unavailable"); sameLocations = await response.json(); renderSameLocations(); } catch (_) { $("sameLookupCount").textContent = "Unavailable"; $("sameLocationResults").innerHTML = "<p class=\"hint\">The location lookup could not be loaded. Enter the SAME code manually.</p>"; } }
function renderSameEventLinks() { $("sameEventLinks").innerHTML = sameEventCodes.map(([code, label]) => `<button type="button" class="same-event" data-event-code="${code}" title="Add ${label}"><strong>${code}</strong><span>${label}</span></button>`).join(""); $("sameEventLinks").querySelectorAll("[data-event-code]").forEach((button) => button.addEventListener("click", () => { addSameValue("events", button.dataset.eventCode); button.classList.add("added"); })); }
$("sameLocationSearch").addEventListener("input", (event) => renderSameLocations(event.target.value));
renderSameEventLinks();
loadSameLocations();
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
