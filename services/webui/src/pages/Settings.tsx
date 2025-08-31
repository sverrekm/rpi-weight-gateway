import React, { useEffect, useState } from 'react'
import {
  Config,
  getConfig,
  saveConfig,
  listDisplayPorts,
  getBrokerStatus,
  brokerRestart,
  brokerStart,
  brokerStop,
  systemUpdate,
} from '../lib/api'

const SettingsPage: React.FC = () => {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [ports, setPorts] = useState<{ device?: string | null; name: string }[]>([])
  const [broker, setBroker] = useState<{ running: boolean; host: string; port: number; config_exists: boolean; control_capable: boolean } | null>(null)
  const [updating, setUpdating] = useState(false)
  const [updateLogs, setUpdateLogs] = useState('')
  const [rebuild, setRebuild] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        setCfg(await getConfig())
      } catch (e) {
        setMsg('Failed to load config')
      }
    })()
  }, [])

  useEffect(() => {
    (async () => {
      try { const r = await listDisplayPorts(); setPorts(r.ports || []) } catch {}
      try { const b = await getBrokerStatus(); setBroker(b) } catch { setBroker(null) }
    })()
  }, [])

  if (!cfg) return <div>Loading...</div>

  const onChange = (k: keyof Config) => (e: any) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setCfg({ ...cfg, [k]: e.target.type === 'checkbox' ? e.target.checked : v })
  }

  const onSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      const newCfg = await saveConfig(cfg)
      setCfg(newCfg)
      setMsg('Saved!')
    } catch (e) {
      setMsg('Save failed')
    } finally {
      setSaving(false)
    }
  }

  const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <label style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 8, alignItems: 'center' }}>
      <div style={{ color: '#6b7280' }}>{label}</div>
      <div>{children}</div>
    </label>
  )

  return (
    <div>
      <h2>Settings</h2>

      {/* MQTT */}
      <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>MQTT</h3>
        <div style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
          <Field label="MQTT Host">
            <input value={cfg.mqtt_host ?? ''} onChange={onChange('mqtt_host')} placeholder="e.g. 192.168.1.10" />
          </Field>
          <Field label="MQTT Port">
            <input type="number" value={cfg.mqtt_port} onChange={onChange('mqtt_port')} />
          </Field>
          <Field label="MQTT User">
            <input value={cfg.mqtt_user ?? ''} onChange={onChange('mqtt_user')} />
          </Field>
          <Field label="MQTT Pass">
            <form onSubmit={(e) => { e.preventDefault(); }} className="w-full">
              <input 
                value={cfg.mqtt_pass ?? ''} 
                onChange={onChange('mqtt_pass')} 
                type="password"
                name="mqtt-password"
                autoComplete="current-password"
                className="w-full"
              />
            </form>
          </Field>
          <Field label="Topics (measure / status / cmd)">
            <input value={cfg.weight_topic} onChange={onChange('weight_topic')} style={{ width: 220 }} />
            <input value={cfg.status_topic} onChange={onChange('status_topic')} style={{ width: 220, marginLeft: 8 }} />
            <input value={cfg.cmd_topic} onChange={onChange('cmd_topic')} style={{ width: 220, marginLeft: 8 }} />
          </Field>
        </div>
      </section>

      {/* Sampling */}
      <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Sampling & Filtering</h3>
        <div style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
          <Field label="GPIO DOUT / SCK">
            <input type="number" value={cfg.gpio_dout} onChange={onChange('gpio_dout')} style={{ width: 100 }} />
            <input type="number" value={cfg.gpio_sck} onChange={onChange('gpio_sck')} style={{ width: 100, marginLeft: 8 }} />
          </Field>
          <Field label="Sample rate (SPS)">
            <input type="number" value={cfg.sample_rate} onChange={onChange('sample_rate')} />
          </Field>
          <Field label="Median window">
            <input type="number" value={cfg.median_window} onChange={onChange('median_window')} />
          </Field>
          <Field label="Scale">
            <input type="number" value={cfg.scale} onChange={onChange('scale')} step={0.0001} />
          </Field>
          <Field label="Offset">
            <input type="number" value={cfg.offset} onChange={onChange('offset')} step={0.0001} />
          </Field>
          <Field label="Max capacity (g)">
            <input type="number" min={0} value={cfg.max_capacity_g} onChange={onChange('max_capacity_g')} />
          </Field>
          <Field label="Demo mode">
            <input type="checkbox" checked={cfg.demo_mode} onChange={onChange('demo_mode')} />
          </Field>
        </div>
      </section>

      {/* Display */}
      <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>Display (ND5052)</h3>
        <div style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
          <Field label="Enable display">
            <input type="checkbox" checked={!!cfg.display_enabled} onChange={onChange('display_enabled')} />
          </Field>
          <Field label="Serial port">
            <select value={cfg.serial_port ?? ''} onChange={onChange('serial_port')}>
              <option value="">Select port</option>
              {ports.map((p, i) => (
                <option key={i} value={p.device ?? ''}>{p.device || ''} {p.name ? `(${p.name})` : ''}</option>
              ))}
            </select>
          </Field>
          <Field label="Baud / Databits / Parity / Stopbits">
            <input type="number" value={cfg.baudrate} onChange={onChange('baudrate')} style={{ width: 120 }} />
            <select value={cfg.databits} onChange={onChange('databits')} style={{ marginLeft: 8 }}>
              {[5,6,7,8].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <select value={cfg.parity} onChange={onChange('parity')} style={{ marginLeft: 8 }}>
              {['N','E','O'].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <select value={cfg.stopbits} onChange={onChange('stopbits')} style={{ marginLeft: 8 }}>
              {[1,2].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
          <Field label="Decimal places (DP)">
            <input type="number" value={cfg.dp} onChange={onChange('dp')} />
          </Field>
          <Field label="Unit">
            <select value={cfg.unit} onChange={onChange('unit')}>
              {['g','kg'].map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </Field>
          <Field label="Address (optional)">
            <input value={cfg.address ?? ''} onChange={onChange('address')} placeholder="e.g. 01" />
          </Field>
        </div>
      </section>

      {/* Save */}
      <div style={{ marginTop: 16 }}>
        <button onClick={onSave} disabled={saving} style={{ padding: '8px 12px' }}>{saving ? 'Saving...' : 'Save settings'}</button>
        <span style={{ marginLeft: 12, color: msg.includes('fail') ? '#dc2626' : '#16a34a' }}>{msg}</span>
      </div>

      {/* Broker */}
      <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 24 }}>
        <h3 style={{ marginTop: 0 }}>Broker</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ color: '#6b7280' }}>Status: {broker ? (broker.running ? 'running' : 'stopped') : 'unknown'}</div>
          <button onClick={async ()=>{ await brokerStart(); setBroker(await getBrokerStatus()) }}>Start</button>
          <button onClick={async ()=>{ await brokerStop(); setBroker(await getBrokerStatus()) }}>Stop</button>
          <button onClick={async ()=>{ await brokerRestart(); setBroker(await getBrokerStatus()) }}>Restart</button>
        </div>
        {!broker?.control_capable && (
          <div style={{ marginTop: 8, color: '#dc2626' }}>Control unavailable: docker socket not mounted in container.</div>
        )}
      </section>

      {/* System update */}
      <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 24 }}>
        <h3 style={{ marginTop: 0 }}>System Update</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={rebuild} onChange={e=>setRebuild(e.target.checked)} /> Rebuild locally
          </label>
          <button disabled={updating} onClick={async ()=>{
            setUpdating(true); setUpdateLogs('');
            try { const r = await systemUpdate(rebuild); setUpdateLogs((r.logs || r.error || '').slice(-4000)) } finally { setUpdating(false) }
          }}>{updating ? 'Updating...' : 'Check & Apply'}</button>
        </div>
        <pre style={{ marginTop: 12, background: '#0b1021', color: '#9ee493', padding: 12, borderRadius: 6, maxHeight: 240, overflow: 'auto' }}>{updateLogs || '—'}</pre>
      </section>

      <div style={{ marginTop: 24, color: '#6b7280' }}>
        Wi‑Fi setup is provided via captive portal when no internet is detected (profile: wifi).
      </div>
    </div>
  )
}

export default SettingsPage
