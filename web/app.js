const $ = (id) => document.getElementById(id);
const fmt = (hz) => `${(hz / 1e6).toFixed(3)} MHz`;
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
async function refresh() { try { render(await api("/api/status")); const reg = await api("/api/registration"); $("registration").textContent = reg.mode.toUpperCase(); $("installation").textContent = reg.installation_id; $("status").textContent = "READY"; $("status").className = "pill ok"; } catch (error) { $("status").textContent = "OFFLINE"; $("log").textContent = error.message; } }
$("scan").onclick = async () => { const state = await api("/api/scan", {method:"POST", body:"{}"}); render(state); if (!state.simulate) { $("audio").hidden = false; $("audio").src = "/api/audio.wav?started=" + Date.now(); $("audio").play().catch(() => {}); } };
$("stop").onclick = async () => { const state = await api("/api/stop", {method:"POST", body:"{}"}); render(state); $("audio").pause(); $("audio").removeAttribute("src"); $("audio").hidden = true; };
$("saveFilter").onclick = async () => { await api("/api/same/filter", {method:"POST", body:JSON.stringify({counties:$("counties").value.split(",").map(v=>v.trim()).filter(Boolean), events:$("events").value.split(",").map(v=>v.trim()).filter(Boolean)})}); };
$("testAlert").onclick = async () => { await api("/api/same/test", {method:"POST", body:JSON.stringify({header:"ZCZC-WXR-TOR-006001+0015-2321800-KXYZ-"})}); await refresh(); };
refresh(); setInterval(refresh, 5000);
