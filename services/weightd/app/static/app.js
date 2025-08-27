/* Minimal UI for rpi-weight-gateway */
const qs = (s) => document.querySelector(s);
const $grams = qs('#grams');
const $stable = qs('#stable');
const $uptime = qs('#uptime');
const $wifi = qs('#wifi');
const $mqtt = qs('#mqtt');
const $version = qs('#version');
const $btnTare = qs('#btnTare');
const $btnZero = qs('#btnZero');
const $btnCal = qs('#btnCalibrate');
const $known = qs('#knownGrams');
const $calibStatus = qs('#calibStatus');
const $cfgForm = qs('#cfgForm');
const $cfgStatus = qs('#cfgStatus');
const $ws = qs('#ws');
const $lastTs = qs('#lastTs');
const $gpioPresets = qs('#gpioPresets');
// Display UI elements
const $dispText = qs('#dispText');
const $dispGrams = qs('#dispGrams');
const $btnDispSendText = qs('#btnDispSendText');
const $btnDispSendGrams = qs('#btnDispSendGrams');
const $dispMsg = qs('#dispMsg');
const $serialPortInput = qs('#serialPortInput');
const $serialPorts = qs('#serialPorts');
const $btnScanPorts = qs('#btnScanPorts');
// Broker UI elements
const $brokerStatus = qs('#brokerStatus');
const $brokerConf = qs('#brokerConf');
const $brokerMsg = qs('#brokerMsg');
const $btnBrokerSave = qs('#btnBrokerSave');
const $btnBrokerRestart = qs('#btnBrokerRestart');
const $btnBrokerStart = qs('#btnBrokerStart');
const $btnBrokerStop = qs('#btnBrokerStop');
let currentCfg = {};
let wsConnected = false;
let pollTimer = null;

function fmtUptime(s) {
  const d = Math.floor(s / 86400);
  s %= 86400;
  const h = Math.floor(s / 3600);
  s %= 3600;
  const m = Math.floor(s / 60);
  s %= 60;
  return `${d}d ${h}h ${m}m ${s}s`;
}

async function loadBroker() {
  // status
  try {
    const rs = await fetch('/api/broker/status');
    if (rs.ok) {
      const s = await rs.json();
      if ($brokerStatus) {
        $brokerStatus.textContent = `Broker: ${s.running ? 'running' : 'stopped'} @ ${s.host}:${s.port}`;
        $brokerStatus.className = 'chip ' + (s.running ? 'ok' : 'bad');
      }
      // enable/disable controls
      const canCtrl = !!s.control_capable;
      if ($btnBrokerRestart) $btnBrokerRestart.disabled = !canCtrl;
      if ($btnBrokerStart) $btnBrokerStart.disabled = !canCtrl;
      if ($btnBrokerStop) $btnBrokerStop.disabled = !canCtrl;
      if (!canCtrl && $brokerMsg) {
        $brokerMsg.textContent = 'Control disabled: Docker socket not mounted in weightd container';
      }
    }
  } catch {}
  // config
  try {
    const rc = await fetch('/api/broker/config');
    if (rc.ok) {
      const j = await rc.json();
      if ($brokerConf && typeof j.content === 'string') $brokerConf.value = j.content;
    }
  } catch {}
}

async function loadHealth() {
  try {
    const r = await fetch('/api/health');
    const j = await r.json();
    $uptime.textContent = `Uptime: ${fmtUptime(j.uptime_s)}`;
    $wifi.textContent = `WiFi: ${j.wifi.connected ? 'connected' : 'disconnected'}${j.wifi.ssid ? ' ('+j.wifi.ssid+')' : ''} ${j.wifi.ip ? j.wifi.ip : ''}`;
    $mqtt.textContent = `MQTT: ${j.mqtt}`;
    $version.textContent = `v${j.version}`;
  } catch (e) {
    $uptime.textContent = 'Uptime: -';
  }
  // Broker bindings
  if ($btnBrokerSave) $btnBrokerSave.addEventListener('click', async ()=>{
    if (!$brokerConf) return;
    $brokerMsg.textContent = 'Saving...';
    try {
      await post('/api/broker/config', { content: $brokerConf.value });
      $brokerMsg.textContent = 'Saved ✓';
      setTimeout(()=> $brokerMsg.textContent='', 1500);
    } catch(e){ $brokerMsg.textContent = 'Error: '+e.message; }
  });
  if ($btnBrokerRestart) $btnBrokerRestart.addEventListener('click', async ()=>{
    $brokerMsg.textContent = 'Restarting...';
    try { await post('/api/broker/restart'); $brokerMsg.textContent = 'Restarted ✓'; loadBroker(); }
    catch(e){ $brokerMsg.textContent = 'Error: '+e.message; }
  });
  if ($btnBrokerStart) $btnBrokerStart.addEventListener('click', async ()=>{
    $brokerMsg.textContent = 'Starting...';
    try { await post('/api/broker/start'); $brokerMsg.textContent = 'Started ✓'; loadBroker(); }
    catch(e){ $brokerMsg.textContent = 'Error: '+e.message; }
  });
  if ($btnBrokerStop) $btnBrokerStop.addEventListener('click', async ()=>{
    $brokerMsg.textContent = 'Stopping...';
    try { await post('/api/broker/stop'); $brokerMsg.textContent = 'Stopped ✓'; loadBroker(); }
    catch(e){ $brokerMsg.textContent = 'Error: '+e.message; }
  });
  // Scan serial ports
  if ($btnScanPorts) $btnScanPorts.addEventListener('click', async ()=>{
    await loadSerialPorts(currentCfg.serial_port || '');
  });
}

async function loadSerialPorts(currentValue) {
  try {
    if (!$serialPorts) return;
    $serialPorts.innerHTML = '';
    const r = await fetch('/api/display/ports');
    if (!r.ok) throw new Error('scan failed');
    const j = await r.json();
    const ports = Array.isArray(j.ports) ? j.ports : [];
    for (const p of ports) {
      const val = p.device || '';
      if (!val) continue;
      const opt = document.createElement('option');
      opt.value = val;
      opt.label = p.name ? `${val} — ${p.name}` : val;
      $serialPorts.appendChild(opt);
    }
    // Set current value into the input
    if ($serialPortInput && currentValue) $serialPortInput.value = currentValue;
  } catch (e) {
    // ignore scan errors silently
  }
}

async function loadConfig() {
  const r = await fetch('/api/config');
  const cfg = await r.json();
  currentCfg = cfg;
  for (const [k, v] of Object.entries(cfg)) {
    const el = $cfgForm.elements.namedItem(k);
    if (!el) continue;
    if (el.type === 'checkbox') el.checked = !!v; else el.value = v ?? '';
  }
  // Populate serial ports after config load to preselect current value
  await loadSerialPorts(cfg.serial_port || '');
}

function toInt(v) { const n = parseInt(v, 10); return Number.isFinite(n) ? n : undefined; }
function toFloat(v) { const n = parseFloat(v); return Number.isFinite(n) ? n : undefined; }

async function saveConfig(e) {
  e.preventDefault();
  // Start from currentCfg to avoid losing values when some inputs are empty
  const body = { ...currentCfg };
  for (const el of $cfgForm.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') { body[el.name] = el.checked; continue; }
    if (el.type === 'number') {
      // Typed parsing by field name
      if (['mqtt_port','gpio_dout','gpio_sck','sample_rate','median_window'].includes(el.name)) {
        const v = toInt(el.value);
        if (v !== undefined) body[el.name] = v;
      } else if (['scale','offset'].includes(el.name)) {
        const v = toFloat(el.value);
        if (v !== undefined) body[el.name] = v;
      } else {
        const v = toFloat(el.value);
        if (v !== undefined) body[el.name] = v;
      }
      continue;
    }
    if (el.value !== '') body[el.name] = el.value; // keep existing if empty
  }
  $cfgStatus.textContent = 'Saving...';
  try {
    const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(await r.text());
    const saved = await r.json().catch(()=>null);
    if (saved) currentCfg = saved;
    await loadConfig();
  await loadBroker();
    $cfgStatus.textContent = 'Saved ✓ (applied)';
    setTimeout(()=> $cfgStatus.textContent = '', 2000);
  } catch (e) {
    $cfgStatus.textContent = 'Error: ' + e.message;
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : null });
  if (!r.ok) throw new Error(await r.text());
  return r.json().catch(()=>({}));
}

function updateWs(status, ok) {
  if (!$ws) return;
  $ws.textContent = `WS: ${status}`;
  $ws.className = 'chip ' + (ok ? 'ok' : 'bad');
}

function setUiConnected(connected) {
  wsConnected = connected;
  [$btnTare, $btnZero, $btnCal].forEach(btn => { if (btn) btn.disabled = !connected; });
  if (!connected) {
    if ($grams) $grams.textContent = '--.-';
    if ($stable) { $stable.textContent = 'no data'; $stable.className = 'stable off'; }
    if ($lastTs) $lastTs.textContent = '—';
  }
}

async function fetchReadingOnce() {
  try {
    const r = await fetch('/api/reading');
    if (!r.ok) throw new Error('read failed');
    const msg = await r.json();
    $grams.textContent = (Math.round(msg.grams * 10) / 10).toFixed(1);
    $stable.textContent = msg.stable ? 'stable' : 'unstable';
    $stable.className = msg.stable ? 'stable on' : 'stable off';
    if ($lastTs) $lastTs.textContent = msg.ts || '—';
    updateWs('polling', true);
    setUiConnected(true);
  } catch (_) {
    updateWs('error', false);
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(fetchReadingOnce, 1000);
  fetchReadingOnce();
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

function connectWS() {
  let proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/weight`);
  updateWs('connecting', false);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    $grams.textContent = (Math.round(msg.grams * 10) / 10).toFixed(1);
    $stable.textContent = msg.stable ? 'stable' : 'unstable';
    $stable.className = msg.stable ? 'stable on' : 'stable off';
    if ($lastTs) $lastTs.textContent = msg.ts || '—';
    updateWs('connected', true);
    setUiConnected(true);
    stopPolling();
  };
  ws.onopen = () => { updateWs('connected', true); setUiConnected(true); stopPolling(); };
  ws.onerror = () => { updateWs('error', false); setUiConnected(false); startPolling(); };
  ws.onclose = () => { updateWs('disconnected', false); setUiConnected(false); startPolling(); setTimeout(connectWS, 2000); };
}

function bindActions() {
  $btnTare.addEventListener('click', async ()=> { try { await post('/api/tare'); } catch(e){} });
  $btnZero.addEventListener('click', async ()=> { try { await post('/api/zero'); } catch(e){} });
  $btnCal.addEventListener('click', async ()=> {
    const val = parseFloat($known.value);
    if (!isFinite(val) || val <= 0) { $calibStatus.textContent = 'Enter valid grams'; return; }
    $calibStatus.textContent = 'Calibrating...';
    try {
      const res = await post('/api/calibrate', { known_grams: val });
      $calibStatus.textContent = `OK. scale=${res.scale?.toFixed ? res.scale.toFixed(6) : res.scale}`;
      setTimeout(()=> $calibStatus.textContent = '', 2500);
    } catch (e) {
      $calibStatus.textContent = 'Error: ' + e.message;
    }
  });
  // Save via button to prevent browser form navigation
  const $btnSave = document.getElementById('btnSave');
  if ($btnSave) $btnSave.addEventListener('click', (e)=> saveConfig(e));
  // Prevent Enter key from submitting the form
  $cfgForm.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); }
  });
  if ($gpioPresets) {
    $gpioPresets.addEventListener('change', () => {
      if (!$gpioPresets.value) return;
      try {
        const preset = JSON.parse($gpioPresets.value);
        for (const [k, v] of Object.entries(preset)) {
          const el = $cfgForm.elements.namedItem(k);
          if (el) el.value = v;
        }
      } catch {}
    });
  }
  // Display test handlers
  if ($btnDispSendText) $btnDispSendText.addEventListener('click', async ()=>{
    if (!$dispText) return;
    $dispMsg.textContent = 'Sending...';
    try { await post('/api/display/test', { text: $dispText.value || '' }); $dispMsg.textContent = 'Sent ✓'; setTimeout(()=> $dispMsg.textContent='', 1500); }
    catch(e){ $dispMsg.textContent = 'Error: ' + e.message; }
  });
  if ($btnDispSendGrams) $btnDispSendGrams.addEventListener('click', async ()=>{
    if (!$dispGrams) return;
    const val = parseFloat($dispGrams.value);
    if (!isFinite(val)) { $dispMsg.textContent = 'Enter a number'; return; }
    $dispMsg.textContent = 'Sending...';
    try { await post('/api/display/test', { grams: val }); $dispMsg.textContent = 'Sent ✓'; setTimeout(()=> $dispMsg.textContent='', 1500); }
    catch(e){ $dispMsg.textContent = 'Error: ' + e.message; }
  });
}

async function init() {
  await loadHealth();
  await loadConfig();
  bindActions();
  setUiConnected(false);
  connectWS();
  // kick off polling as immediate fallback until WS connects
  startPolling();
  setInterval(loadHealth, 5000);
}

document.addEventListener('DOMContentLoaded', init);
