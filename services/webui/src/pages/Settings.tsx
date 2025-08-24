import React, { useEffect, useState } from 'react'
import { Config, getConfig, saveConfig } from '../lib/api'

const SettingsPage: React.FC = () => {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    (async () => {
      try {
        setCfg(await getConfig())
      } catch (e) {
        setMsg('Failed to load config')
      }
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
      <div style={{ display: 'grid', gap: 12, maxWidth: 560 }}>
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
          <input value={cfg.mqtt_pass ?? ''} onChange={onChange('mqtt_pass')} type="password" />
        </Field>
        <Field label="Topics (measure/status/cmd)">
          <input value={cfg.weight_topic} onChange={onChange('weight_topic')} style={{ width: 180 }} />
          <input value={cfg.status_topic} onChange={onChange('status_topic')} style={{ width: 180, marginLeft: 8 }} />
          <input value={cfg.cmd_topic} onChange={onChange('cmd_topic')} style={{ width: 180, marginLeft: 8 }} />
        </Field>
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
          <input type="number" value={cfg.scale} onChange={onChange('scale')} step="0.0001" />
        </Field>
        <Field label="Offset">
          <input type="number" value={cfg.offset} onChange={onChange('offset')} step="0.0001" />
        </Field>
        <Field label="Demo mode">
          <input type="checkbox" checked={cfg.demo_mode} onChange={onChange('demo_mode')} />
        </Field>
      </div>
      <div style={{ marginTop: 16 }}>
        <button onClick={onSave} disabled={saving} style={{ padding: '8px 12px' }}>{saving ? 'Saving...' : 'Save'}</button>
        <span style={{ marginLeft: 12, color: '#16a34a' }}>{msg}</span>
      </div>
      <div style={{ marginTop: 24, color: '#6b7280' }}>
        Wi-Fi setup is provided via captive portal when no internet is detected (profile: wifi). Connect to AP and
        complete setup, then return here.
      </div>
    </div>
  )
}

export default SettingsPage
