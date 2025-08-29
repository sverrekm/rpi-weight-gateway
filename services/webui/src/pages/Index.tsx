import React, { useEffect, useRef, useState } from 'react'
import { getReading, getConfig, tare, zero } from '../lib/api'

type R = { grams: number; ts: string; stable: boolean }

const IndexPage: React.FC = () => {
  const [reading, setReading] = useState<R | null>(null)
  const [status, setStatus] = useState<string>('connecting...')
  const [maxCap, setMaxCap] = useState<number>(0)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Load configuration for max capacity
    (async () => {
      try {
        const cfg = await getConfig()
        setMaxCap(cfg.max_capacity_g || 0)
      } catch {}
    })()

    const wsUrl = (() => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      return `${proto}://${location.host}/ws/weight`
    })()
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onopen = () => setStatus('live')
    ws.onclose = () => setStatus('disconnected')
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data) as R
      setReading(data)
    }
    return () => ws.close()
  }, [])

  useEffect(() => {
    // Fallback poll if WS not working
    let t: any
    if (!reading) {
      t = setInterval(async () => {
        try { setReading(await getReading()) } catch {}
      }, 1000)
    }
    return () => clearInterval(t)
  }, [])

  const grams = reading ? reading.grams.toFixed(2) : '---'
  const stable = reading?.stable
  const overCap = !!reading && maxCap > 0 && reading.grams > maxCap

  return (
    <div style={{ textAlign: 'center', maxWidth: 600, margin: '0 auto' }}>
      {overCap && (
        <div style={{ background: '#fee2e2', color: '#991b1b', padding: '12px 16px', border: '1px solid #fecaca', borderRadius: 8, marginBottom: 24, textAlign: 'left' }}>
          ⚠️ Over capacity: {reading!.grams.toFixed(2)} g exceeds {maxCap} g
        </div>
      )}
      
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 32, marginBottom: 24 }}>
        <div style={{ fontSize: 72, fontWeight: 800, letterSpacing: -2, margin: '0 0 8px 0', color: stable ? '#059669' : '#6b7280' }}>
          {grams} g
        </div>
        <div style={{ fontSize: 18, color: '#6b7280', marginBottom: 24 }}>
          {stable ? '✅ Stable' : '⏳ Measuring...'}
        </div>
        
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button 
            onClick={() => tare()} 
            style={{ 
              padding: '12px 24px', 
              fontSize: 16, 
              fontWeight: 600,
              background: '#2563eb', 
              color: '#fff', 
              border: 'none', 
              borderRadius: 8,
              cursor: 'pointer'
            }}
          >
            Tare
          </button>
          <button 
            onClick={() => zero()} 
            style={{ 
              padding: '12px 24px', 
              fontSize: 16, 
              fontWeight: 600,
              background: '#dc2626', 
              color: '#fff', 
              border: 'none', 
              borderRadius: 8,
              cursor: 'pointer'
            }}
          >
            Zero
          </button>
        </div>
      </div>
      
      <div style={{ color: '#6b7280', fontSize: 14 }}>
        Connection: <span style={{ color: status === 'live' ? '#059669' : '#dc2626', fontWeight: 600 }}>{status}</span>
      </div>
    </div>
  )
}

export default IndexPage
