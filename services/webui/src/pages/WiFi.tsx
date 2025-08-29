import React, { useEffect, useState } from 'react'
import { getWifiStatus, scanWifi, connectWifi } from '../lib/api'

const WiFiPage: React.FC = () => {
  const [status, setStatus] = useState<{ connected: boolean; ssid?: string; ip?: string } | null>(null)
  const [nets, setNets] = useState<{ ssid: string; signal?: number; security?: string }[]>([])
  const [selected, setSelected] = useState('')
  const [psk, setPsk] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    try { setStatus(await getWifiStatus()) } catch {}
  }
  const scan = async () => {
    setMsg('Scanning...')
    try { const r = await scanWifi(); setNets(r.networks || []); setMsg('') } catch { setMsg('Scan failed') }
  }

  useEffect(() => { refresh(); scan(); }, [])

  const onConnect = async () => {
    if (!selected) { setMsg('Select SSID'); return }
    setLoading(true); setMsg('Connecting...')
    try {
      const r = await connectWifi(selected, psk)
      if (r.error) { setMsg('Error: ' + r.error) }
      else { setMsg('Connected ✓'); await refresh() }
    } catch (e:any) { setMsg('Error: ' + (e.message || 'failed')) }
    finally { setLoading(false) }
  }

  return (
    <div>
      <h2>Wi‑Fi</h2>
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
        <div style={{ marginBottom: 8, color: '#6b7280' }}>
          Status: {status ? (status.connected ? `connected to ${status.ssid} (${status.ip||'-'})` : 'disconnected') : '—'}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={selected} onChange={e=>setSelected(e.target.value)}>
            <option value="">Select SSID</option>
            {nets.map((n,i)=> (
              <option key={i} value={n.ssid}>{n.ssid} {typeof n.signal==='number' ? `(${n.signal}%)` : ''}</option>
            ))}
          </select>
          <input type="password" value={psk} onChange={e=>setPsk(e.target.value)} placeholder="Password (leave empty if open)" />
          <button onClick={onConnect} disabled={loading}>{loading ? 'Connecting...' : 'Connect'}</button>
          <button onClick={scan} disabled={loading}>Rescan</button>
        </div>
        <div style={{ marginTop: 8, color: msg.startsWith('Error') ? '#dc2626' : '#16a34a' }}>{msg}</div>
      </div>
      <div style={{ marginTop: 16, color: '#6b7280' }}>Uses nmcli if available, falls back to wpa_cli.</div>
    </div>
  )
}

export default WiFiPage
