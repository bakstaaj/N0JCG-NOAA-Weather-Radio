const $ = (id) => document.getElementById(id);
const fmt = (hz) => `${(hz / 1e6).toFixed(3)} MHz`;
let audioAbort = null;
let audioContext = null;
let audioNextStart = 0;
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
  const sameFilter = state.same_filter || {};
  if (document.activeElement?.id !== "counties") $("counties").value = (sameFilter.counties || []).join(",");
  if (document.activeElement?.id !== "events") $("events").value = (sameFilter.events || []).join(",");
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
async function api(path, options) { const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options}); const data = await response.json(); const log = $("log"); if (log) log.textContent = JSON.stringify(data, null, 2); if (!response.ok) throw new Error(data.error); return data; }
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
    const log = $("log"); if (log) log.textContent = error.message;
  }
}
async function listen() {
  let state = await api("/api/status");
  if (!state.running) state = await api("/api/scan", {method:"POST", body:"{}"});
  render(state);
  if (state.simulate) { const log = $("log"); if (log) log.textContent = "Simulation mode has no live audio stream."; return; }
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
  audioNextStart = audioContext.currentTime + 0.04;
  $("audioStatus").hidden = false;
  $("audioStatus").textContent = "Live WAV audio connected - use system/browser volume.";
  audioChunkLoop(audioAbort.signal).catch((error) => { if (error.name !== "AbortError") { $("audioStatus").textContent = error.message; } });
}
async function audioChunkLoop(signal) {
  while (!signal.aborted && audioContext) {
    const response = await fetch("/api/audio.chunk.wav?chunk=" + Date.now(), {signal});
    if (response.status === 409 || response.status === 503) { await new Promise((resolve) => setTimeout(resolve, 250)); continue; }
    if (!response.ok) throw new Error("finite WAV audio chunk unavailable");
    const buffer = await audioContext.decodeAudioData(await response.arrayBuffer());
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    const startAt = Math.max(audioNextStart, audioContext.currentTime + 0.04);
    source.start(startAt);
    audioNextStart = startAt + buffer.duration;
  }
}
function stopPcmAudio() {
  if (audioAbort) audioAbort.abort(); audioAbort = null;
  if (audioContext) { audioContext.close(); audioContext = null; }
  audioNextStart = 0;
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
$("listen").onclick = () => listen().catch((error) => { const log = $("log"); if (log) log.textContent = error.message; });
$("stop").onclick = async () => { stopPcmAudio(); const state = await api("/api/stop", {method:"POST", body:"{}"}); render(state); };
let sameLocations = [];
const sameEventCodes = [["ALL", "All event types"], ["TOR", "Tornado Warning"], ["SVR", "Severe Thunderstorm Warning"], ["FFW", "Flash Flood Warning"], ["FLW", "Flood Warning"], ["HWW", "High Wind Warning"], ["EVI", "Evacuation Immediate"], ["RWT", "Required Weekly Test"]];
const escapeHtml = (value) => String(value).replace(/[&<>\"']/g, (character) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;"}[character]));
function addSameValue(id, value) { const input = $(id); let values = input.value.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean); if (value === "ALL") values = ["ALL"]; else { values = values.filter((item) => item !== "ALL"); if (!values.includes(value)) values.push(value); } input.value = values.join(","); input.focus(); }
function renderSameLocations(query = "") { const tokens = query.trim().toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); const matches = sameLocations.filter((item) => { const fields = [item.name, item.state, item.code].map((value) => String(value).toLowerCase().replace(/[^a-z0-9]/g, "")); return !tokens.length || tokens.every((token) => fields.some((field) => field.includes(token))); }).slice(0, 30); $("sameLookupCount").textContent = tokens.length ? `${matches.length}${matches.length === 30 ? "+" : ""} matches` : `${sameLocations.length} counties`; $("sameLocationResults").innerHTML = matches.length ? matches.map((item) => `<button type="button" class="same-result" data-same-code="${item.code}" title="Add ${escapeHtml(item.name)}, ${item.state}"><span><strong>${escapeHtml(item.name)}</strong><small>${item.state} · SAME ${item.code}</small></span><span class="same-add">Add</span></button>`).join("") : "<p class=\"hint\">No county matches. Try a county name, state abbreviation, or six-digit code.</p>"; $("sameLocationResults").querySelectorAll("[data-same-code]").forEach((button) => button.addEventListener("click", () => { addSameValue("counties", button.dataset.sameCode); button.classList.add("added"); button.querySelector(".same-add").textContent = "Added"; })); }
async function loadSameLocations() { try { const response = await fetch("/data/same-codes.json", {cache:"no-store"}); if (!response.ok) throw new Error("lookup unavailable"); sameLocations = await response.json(); renderSameLocations(); } catch (_) { $("sameLookupCount").textContent = "Unavailable"; $("sameLocationResults").innerHTML = "<p class=\"hint\">The location lookup could not be loaded. Enter the SAME code manually.</p>"; } }
function renderSameEventLinks() { $("sameEventLinks").innerHTML = sameEventCodes.map(([code, label]) => `<button type="button" class="same-event" data-event-code="${code}" title="Add ${label}"><strong>${code}</strong><span>${label}</span></button>`).join(""); $("sameEventLinks").querySelectorAll("[data-event-code]").forEach((button) => button.addEventListener("click", () => { addSameValue("events", button.dataset.eventCode); button.classList.add("added"); })); }
$("sameLocationSearch").addEventListener("input", (event) => renderSameLocations(event.target.value));
renderSameEventLinks();
loadSameLocations();
$("saveFilter").onclick = async () => { const status = $("sameFilterStatus"); const button = $("saveFilter"); button.disabled = true; status.textContent = "Saving…"; try { await api("/api/same/filter", {method:"POST", body:JSON.stringify({counties:$("counties").value.split(",").map(v=>v.trim()).filter(Boolean), events:$("events").value.split(",").map(v=>v.trim()).filter(Boolean)})}); status.textContent = "SAME settings updated."; } catch (error) { status.textContent = error.message; } finally { button.disabled = false; } };
setInterval(() => {
  if (trialRemainingSeconds != null && !trialPaused) {
    trialRemainingSeconds = Math.max(0, trialRemainingSeconds - 1);
    $("registration").textContent = trialRemainingSeconds ? `TRIAL ${formatTrialTime(trialRemainingSeconds)}` : "TRIAL PAUSED";
    if (!trialRemainingSeconds) $("installation").textContent = "RESTART REQUIRED";
  }
}, 1000);
refresh(); setInterval(refresh, 5000);
