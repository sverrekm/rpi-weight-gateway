export type Reading = { grams: number; ts: string; stable: boolean }
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
  demo_mode: boolean
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

export async function zero() {
  await fetch(`${base}/api/zero`, { method: 'POST' })
}

export async function calibrate(known_grams: number) {
  const r = await fetch(`${base}/api/calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ known_grams }),
  })
  if (!r.ok) throw new Error('calibrate failed')
  return r.json() as Promise<{ status: string; scale: number }>
}
