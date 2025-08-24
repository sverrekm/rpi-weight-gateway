import React, { useEffect, useRef, useState } from 'react'
import { getReading, tare, zero } from '../lib/api'

type R = { grams: number; ts: string; stable: boolean }

const IndexPage: React.FC = () => {
  const [reading, setReading] = useState<R | null>(null)
  const [status, setStatus] = useState<string>('connecting...')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
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

  return (
    <div>
      <h2>Live weight</h2>
      <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: -1, margin: '24px 0' }}>
        {grams} g {stable ? '✅' : '...'}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => tare()} style={{ padding: '8px 12px' }}>Tare</button>
        <button onClick={() => zero()} style={{ padding: '8px 12px' }}>Zero</button>
      </div>
      <div style={{ marginTop: 16, color: '#6b7280' }}>Status: {status}</div>
    </div>
  )
}

export default IndexPage
