export type Reading = { grams: number; ts: string; stable: boolean }
export type UserPreferences = {
  unit: 'g' | 'kg'
}

export type Config = {
  mqtt_host?: string | null
  mqtt_port: number
  mqtt_user?: string | null
  mqtt_pass?: string | null
  weight_topic: string
  status_topic: string
  cmd_topic: string
  gpio_dout: number
  gpio_sck: number
  sample_rate: number
  median_window: number
  scale: number
  offset: number
  max_capacity_g: number
  demo_mode: boolean
  // Display (ND5052)
  display_enabled: boolean
  serial_port?: string | null
  baudrate: number
  databits: number
  parity: string
  stopbits: number
  dp: number
  unit: string
  address?: string | null
}

const base = '' // same origin (served by backend)

export async function getReading(): Promise<Reading> {
  const r = await fetch(`${base}/api/reading`)
  if (!r.ok) throw new Error('reading failed')
  return r.json()
}

export async function getConfig(): Promise<Config> {
  const r = await fetch(`${base}/api/config`)
  if (!r.ok) throw new Error('config failed')
  return r.json()
}

export async function saveConfig(cfg: Config): Promise<Config> {
  const r = await fetch(`${base}/api/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  })
  if (!r.ok) throw new Error('save failed')
  return r.json()
}

export async function tare() {
  await fetch(`${base}/api/tare`, { method: 'POST' })
}

export const zero = async () => {
  const response = await fetch('/api/zero', { 
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
};

export const updateDisplayUnit = async (unit: string) => {
  const response = await fetch('/api/display/unit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unit })
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || 'Failed to update display unit');
  }
  
  return response.json();
};

export interface ApStatus {
  enabled: boolean;
  ssid?: string;
  ip_address?: string;
  status?: string;
  error?: string;
}

export const getApStatus = (): Promise<ApStatus> =>
  fetch('/api/wifi/ap/status').then(r => r.json())

export const setApMode = (enabled: boolean): Promise<{ status: string }> =>
  fetch(`/api/wifi/ap/${enabled ? 'enable' : 'disable'}`, {
    method: 'POST'
  }).then(r => r.json())

export const getPreferences = (): Promise<UserPreferences> =>
  fetch('/api/preferences').then(r => r.json())

export const updatePreferences = (prefs: UserPreferences) =>
  fetch('/api/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs)
  }).then(r => r.json())

export async function calibrate(known_grams: number) {
  const r = await fetch(`${base}/api/calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ known_grams }),
  })
  if (!r.ok) throw new Error('calibrate failed')
  return r.json() as Promise<{ status: string; scale: number }>
}

// Broker APIs
export async function getBrokerStatus(): Promise<{ running: boolean; host: string; port: number; config_exists: boolean; control_capable: boolean }>{
  const r = await fetch(`${base}/api/broker/status`)
  if (!r.ok) throw new Error('broker status failed')
  return r.json()
}

export async function getBrokerConfig(): Promise<{ content: string }>{
  const r = await fetch(`${base}/api/broker/config`)
  if (!r.ok) throw new Error('broker config failed')
  return r.json()
}

export async function setBrokerConfig(content: string): Promise<{ status: string }>{
  const r = await fetch(`${base}/api/broker/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  })
  if (!r.ok) throw new Error('set broker config failed')
  return r.json()
}

export async function brokerRestart() { await fetch(`${base}/api/broker/restart`, { method: 'POST' }) }
export async function brokerStart() { await fetch(`${base}/api/broker/start`, { method: 'POST' }) }
export async function brokerStop() { await fetch(`${base}/api/broker/stop`, { method: 'POST' }) }

// Display APIs
export async function listDisplayPorts(): Promise<{ ports: { device?: string|null; name: string }[] }>{
  const r = await fetch(`${base}/api/display/ports`)
  if (!r.ok) throw new Error('list ports failed')
  return r.json()
}

export async function displayTest(payload: { text?: string; grams?: number }): Promise<{ status?: string; error?: string }>{
  const r = await fetch(`${base}/api/display/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return r.json()
}

// System update
export async function systemUpdate(rebuild: boolean): Promise<{ status: string; action?: string; logs?: string; error?: string }>{
  const r = await fetch(`${base}/api/system/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rebuild })
  })
  return r.json()
}

// Wi-Fi APIs
export async function getWifiStatus(): Promise<{ connected: boolean; ssid?: string; ip?: string }>{
  const r = await fetch(`${base}/api/wifi/status`)
  if (!r.ok) throw new Error('wifi status failed')
  return r.json()
}

export async function scanWifi(): Promise<{ networks: { ssid: string; signal?: number; security?: string }[] }>{
  const r = await fetch(`${base}/api/wifi/scan`)
  if (!r.ok) throw new Error('wifi scan failed')
  return r.json()
}

export async function connectWifi(ssid: string, psk?: string): Promise<{ status?: string; error?: string; tool?: string; output?: string }>{
  const r = await fetch(`${base}/api/wifi/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ssid, psk })
  })
  return r.json()
}
