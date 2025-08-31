import React, { useEffect, useRef, useState } from 'react'
import { getReading, getConfig, tare, zero, updateDisplayUnit, getPreferences, updatePreferences } from '../lib/api'

type R = { grams: number; ts: string; stable: boolean }

const IndexPage: React.FC = () => {
  const [reading, setReading] = useState<R | null>(null)
  const [status, setStatus] = useState<string>('connecting...')
  const [maxCap, setMaxCap] = useState<number>(0)
  const [unit, setUnit] = useState<'g' | 'kg'>('g')
  const [displayUnit, setDisplayUnit] = useState<'g' | 'kg'>('g')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Load configuration for max capacity and user preferences
    (async () => {
      try {
        const [cfg, prefs] = await Promise.all([
          getConfig(),
          getPreferences().catch(() => ({ unit: 'g' }))
        ])
        setMaxCap(cfg.max_capacity_g || 0)
        // Ensure the unit is either 'g' or 'kg'
        const validUnit = prefs.unit === 'kg' ? 'kg' : 'g'
        setUnit(validUnit)
        setDisplayUnit(validUnit)
      } catch (e) {
        console.error('Failed to load config or preferences:', e)
      }
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

  // Update display unit and save preference when unit changes
  useEffect(() => {
    if (unit !== displayUnit) {
      Promise.all([
        updateDisplayUnit(unit).catch(console.error),
        updatePreferences({ unit })
      ]).catch(console.error)
      setDisplayUnit(unit)
    }
  }, [unit])

  // Unit conversion and formatting
  const formatValue = (grams: number) => {
    if (unit === 'kg') {
      const kg = grams / 1000
      return kg.toFixed(1).replace('.', ',')
    }
    return grams.toFixed(2).replace('.', ',')
  }
  
  const displayValue = reading ? formatValue(reading.grams) : '---'
  const stable = reading?.stable
  const overCap = !!reading && maxCap > 0 && reading.grams > maxCap

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '20px' }}>
      {overCap && (
        <div style={{ 
          background: '#fee2e2', 
          color: '#991b1b', 
          padding: '12px 16px', 
          border: '1px solid #fecaca', 
          borderRadius: 8, 
          marginBottom: 24, 
          textAlign: 'left' 
        }}>
          ⚠️ Over capacity: {formatValue(reading!.grams)} {unit} exceeds {unit === 'kg' ? (maxCap / 1000).toFixed(1).replace('.', ',') : maxCap} {unit}
        </div>
      )}
      
      <div style={{ 
        background: '#fff', 
        border: '1px solid #e5e7eb', 
        borderRadius: 12, 
        padding: 32, 
        marginBottom: 24,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '24px'
        }}>
          <div style={{ fontSize: 72, fontWeight: 800, letterSpacing: -2, color: stable ? '#059669' : '#6b7280' }}>
            {displayValue} {unit}
          </div>
          
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
            marginTop: '16px',
            width: '100%',
            maxWidth: '300px'
          }}>
            <div style={{ 
              fontSize: 14, 
              fontWeight: 600, 
              color: '#4b5563',
              marginBottom: '4px'
            }}>
              Display Unit
            </div>
            <div style={{ 
              display: 'flex', 
              background: '#f3f4f6', 
              borderRadius: 8, 
              padding: 4,
              width: '100%',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={() => setUnit('g')}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  fontSize: 15,
                  fontWeight: 600,
                  background: unit === 'g' ? '#2563eb' : 'transparent',
                  color: unit === 'g' ? '#fff' : '#4b5563',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  whiteSpace: 'nowrap',
                  boxShadow: unit === 'g' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                Grams (g)
              </button>
              <div style={{ width: '8px' }} />
              <button
                onClick={() => setUnit('kg')}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  fontSize: 15,
                  fontWeight: 600,
                  background: unit === 'kg' ? '#2563eb' : 'transparent',
                  color: unit === 'kg' ? '#fff' : '#4b5563',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  whiteSpace: 'nowrap',
                  boxShadow: unit === 'kg' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                Kilograms (kg)
              </button>
            </div>
          </div>
          
          <div style={{ 
            fontSize: 18, 
            color: stable ? '#059669' : '#6b7280',
            marginTop: '8px',
            padding: '8px 16px',
            background: stable ? '#ecfdf5' : '#f9fafb',
            borderRadius: '6px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            {stable ? '✅ Stabil måling' : '⏳ Måler...'}
          </div>
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
