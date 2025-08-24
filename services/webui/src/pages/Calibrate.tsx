import React, { useEffect, useState } from 'react'
import { calibrate, getReading, tare } from '../lib/api'

const CalibratePage: React.FC = () => {
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [known, setKnown] = useState<number>(100)
  const [grams, setGrams] = useState<string>('---')
  const [scale, setScale] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    let t: number
    if (step !== 3) {
      t = setInterval(async () => {
        try { const r = await getReading(); setGrams(r.grams.toFixed(2)) } catch {}
      }, 500)
    }
    return () => clearInterval(t)
  }, [step])

  const doTare = async () => {
    setMsg('Taring...')
    try { await tare(); setMsg('Tare done'); setStep(2) } catch { setMsg('Tare failed') }
  }

  const doCalibrate = async () => {
    setMsg('Calibrating...')
    try {
      const res = await calibrate(known)
      setScale(res.scale)
      setMsg('Calibration saved')
      setStep(3)
    } catch {
      setMsg('Calibration failed')
    }
  }

  return (
    <div>
      <h2>Calibration wizard</h2>
      {step === 1 && (
        <div>
          <p>1) Remove all weight from the scale, then press Tare.</p>
          <button onClick={doTare} style={{ padding: '8px 12px' }}>Tare</button>
        </div>
      )}
      {step === 2 && (
        <div>
          <p>2) Place a known mass on the scale. Enter its weight in grams and press Calibrate.</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="number" value={known} onChange={(e) => setKnown(Number(e.target.value))} />
            <button onClick={doCalibrate} style={{ padding: '8px 12px' }}>Calibrate</button>
          </div>
          <div style={{ marginTop: 12, color: '#6b7280' }}>Live: {grams} g</div>
        </div>
      )}
      {step === 3 && (
        <div>
          <p>Done! Scale factor: <b>{scale?.toFixed(6)}</b></p>
        </div>
      )}
      <div style={{ marginTop: 16, color: '#16a34a' }}>{msg}</div>
    </div>
  )
}

export default CalibratePage
