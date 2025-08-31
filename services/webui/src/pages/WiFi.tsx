import React, { useEffect, useState } from 'react'
import { 
  getWifiStatus, 
  scanWifi, 
  connectWifi, 
  getApStatus, 
  setApMode, 
  getWifiStatus as refreshWifiStatus,
  type ApStatus
} from '../lib/api'

interface WifiStatus {
  connected: boolean;
  ssid?: string;
  ip?: string;
}

const WiFiPage: React.FC = () => {
  const [status, setStatus] = useState<WifiStatus | null>(null)
  const [nets, setNets] = useState<{ ssid: string; signal?: number; security?: string }[]>([])
  const [selected, setSelected] = useState('')
  const [psk, setPsk] = useState('')
  const [msg, setMsg] = useState<{text: string; isError: boolean}>({text: '', isError: false})
  const [loading, setLoading] = useState(false)
  const [apStatus, setApStatus] = useState<ApStatus>({ 
    enabled: false, 
    ssid: 'rpi-weight-gateway',
    status: 'unknown'
  })
  const [apLoading, setApLoading] = useState(false)

  const refreshApStatus = async () => {
    try {
      setApLoading(true)
      const status = await getApStatus()
      setApStatus(prev => ({
        ...prev,
        ...status,
        enabled: status.status === 'active' || status.enabled
      }))
      return status
    } catch (e) {
      const error = e instanceof Error ? e.message : 'Failed to get AP status'
      console.error('AP status error:', error)
      setMsg({text: `Error: ${error}`, isError: true})
      return null
    } finally {
      setApLoading(false)
    }
  }

  const toggleAp = async (enabled: boolean) => {
    setApLoading(true)
    setMsg({text: enabled ? 'Enabling access point...' : 'Disabling access point...', isError: false})
    
    try {
      const result = await setApMode(enabled)
      
      // Wait a bit for the service to start/stop
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      const newStatus = await refreshApStatus()
      
      if (enabled && (!newStatus || !newStatus.enabled)) {
        throw new Error('Failed to enable access point')
      }
      
      setMsg({ 
        text: `Access point ${enabled ? 'enabled' : 'disabled'} successfully`, 
        isError: false 
      })
      
      // Refresh WiFi status after AP state change
      await refreshWifiStatus().then(setStatus).catch(console.error)
      
      return true
    } catch (e) {
      const error = e instanceof Error ? e.message : 'Operation failed'
      console.error('AP toggle error:', error)
      setMsg({ 
        text: `Failed to ${enabled ? 'enable' : 'disable'} access point: ${error}`, 
        isError: true 
      })
      return false
    } finally {
      setApLoading(false)
    }
  }

  const refresh = async () => {
    try { 
      const status = await getWifiStatus()
      setStatus(status)
      return status
    } catch (e) {
      console.error('Failed to refresh WiFi status:', e)
      return null
    }
  }
  
  const scan = async () => {
    setMsg({text: 'Scanning for networks...', isError: false})
    try { 
      const r = await scanWifi(); 
      setNets(r.networks || []); 
      setMsg({text: 'Scan completed', isError: false}) 
      return r.networks || []
    } catch (e) { 
      const error = e instanceof Error ? e.message : 'Scan failed'
      setMsg({text: `Scan failed: ${error}`, isError: true}) 
      return []
    }
  }

  useEffect(() => {
    // Initial load
    const init = async () => {
      try {
        await Promise.all([
          refresh(),
          scan(),
          refreshApStatus()
        ])
      } catch (e) {
        console.error('Initialization error:', e)
      }
    }
    
    init()
    
    // Set up periodic refresh
    const interval = setInterval(() => {
      refresh()
      refreshApStatus()
    }, 30000) // Refresh every 30 seconds
    
    return () => clearInterval(interval)
  }, [])

  const onConnect = async () => {
    if (!selected) { 
      setMsg({text: 'Please select a network', isError: true}); 
      return 
    }
    
    setLoading(true); 
    setMsg({text: 'Connecting to network...', isError: false})
    
    try {
      const r = await connectWifi(selected, psk)
      if (r.error) { 
        throw new Error(r.error || 'Connection failed')
      }
      
      // Wait a bit for the connection to establish
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      // Refresh both WiFi and AP status
      await Promise.all([
        refresh(),
        refreshApStatus()
      ])
      
      setMsg({text: `Connected to ${selected} ✓`, isError: false})
      return true
    } catch (e: any) { 
      const error = e instanceof Error ? e.message : 'Connection failed'
      setMsg({text: `Connection failed: ${error}`, isError: true})
      return false
    } finally { 
      setLoading(false) 
    }
  }

  return (
    <div>
      <h2>Wi‑Fi</h2>
      <div style={{ 
        background: '#fff', 
        border: '1px solid #e5e7eb', 
        borderRadius: 8, 
        padding: 16, 
        marginBottom: 16,
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
      }}>
        <div style={{ 
          marginBottom: 16, 
          display: 'flex', 
          flexDirection: 'column',
          gap: '12px'
        }}>
          {/* WiFi Status */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '8px 0',
            borderBottom: '1px solid #f3f4f6'
          }}>
            <div>
              <h3 style={{ margin: '0 0 4px 0', color: '#1f2937' }}>WiFi Connection</h3>
              <div style={{ color: '#6b7280', fontSize: '0.9em' }}>
                {status ? (
                  status.connected ? (
                    <>
                      <span style={{ color: '#10b981', fontWeight: 500 }}>Connected</span> to {status.ssid} 
                      {status.ip && <>({status.ip})</>}
                    </>
                  ) : 'Disconnected'
                ) : 'Loading...'}
              </div>
            </div>
            <button 
              onClick={() => refresh()}
              style={{
                padding: '4px 12px',
                borderRadius: 4,
                border: '1px solid #e5e7eb',
                background: '#f9fafb',
                color: '#4b5563',
                cursor: 'pointer',
                fontSize: '0.9em',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>⟳</span> Refresh
            </button>
          </div>
          
          {/* Access Point Status */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '8px 0'
          }}>
            <div>
              <h3 style={{ margin: '0 0 4px 0', color: '#1f2937' }}>Access Point</h3>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                color: '#6b7280',
                fontSize: '0.9em'
              }}>
                <span>Status: </span>
                <span style={{ 
                  color: apStatus.status === 'active' ? '#10b981' : '#6b7280',
                  fontWeight: apStatus.status === 'active' ? 500 : 'normal'
                }}>
                  {apStatus.status?.toUpperCase() || 'UNKNOWN'}
                </span>
                {apStatus.ssid && (
                  <span>• SSID: <strong>{apStatus.ssid}</strong></span>
                )}
                {apStatus.ip_address && (
                  <span>• IP: <code>{apStatus.ip_address}</code></span>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button 
                onClick={() => toggleAp(!apStatus.enabled)}
                disabled={apLoading || loading}
                style={{
                  padding: '6px 16px',
                  borderRadius: 4,
                  border: '1px solid #e5e7eb',
                  background: apStatus.status === 'active' ? '#ef4444' : '#10b981',
                  color: 'white',
                  fontWeight: 500,
                  cursor: (apLoading || loading) ? 'not-allowed' : 'pointer',
                  opacity: (apLoading || loading) ? 0.7 : 1,
                  minWidth: '100px',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {apLoading ? (
                  <span className="spinner">⏳</span>
                ) : apStatus.status === 'active' ? (
                  'Turn OFF'
                ) : (
                  'Turn ON'
                )}
              </button>
            </div>
          </div>
          
          {/* Status Message */}
          {msg.text && (
            <div style={{
              padding: '8px 12px',
              borderRadius: '4px',
              background: msg.isError ? '#fef2f2' : '#f0fdf4',
              borderLeft: `3px solid ${msg.isError ? '#ef4444' : '#10b981'}`,
              color: msg.isError ? '#991b1b' : '#166534',
              fontSize: '0.9em',
              marginTop: '4px'
            }}>
              {msg.text}
            </div>
          )}
        </div>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column',
          gap: '12px',
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid #f3f4f6'
        }}>
          <h3 style={{ margin: '0 0 8px 0', color: '#1f2937' }}>Connect to WiFi Network</h3>
          
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            <select 
              value={selected} 
              onChange={e => setSelected(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                minWidth: '200px',
                flex: '1 1 200px',
                maxWidth: '100%'
              }}
            >
              <option value="">Select a network...</option>
              {nets.length === 0 ? (
                <option disabled>No networks found</option>
              ) : (
                nets.map((n, i) => (
                  <option key={i} value={n.ssid}>
                    {n.ssid} 
                    {typeof n.signal === 'number' && ` (${n.signal}%)`}
                    {n.security && ` [${n.security}]`}
                  </option>
                ))
              )}
            </select>
            
            <input 
              type="password" 
              value={psk} 
              onChange={e => setPsk(e.target.value)} 
              placeholder="Password (if required)" 
              style={{
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid #d1d5db',
                flex: '1 1 200px',
                maxWidth: '100%'
              }}
            />
            
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                onClick={onConnect} 
                disabled={loading || !selected}
                style={{
                  padding: '8px 16px',
                  borderRadius: '4px',
                  border: 'none',
                  background: loading || !selected ? '#9ca3af' : '#3b82f6',
                  color: 'white',
                  fontWeight: 500,
                  cursor: (loading || !selected) ? 'not-allowed' : 'pointer',
                  opacity: (loading || !selected) ? 0.7 : 1,
                  minWidth: '100px',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {loading ? (
                  <span className="spinner">⏳</span>
                ) : (
                  'Connect'
                )}
              </button>
              
              <button 
                onClick={scan} 
                disabled={loading}
                style={{
                  padding: '8px 16px',
                  borderRadius: '4px',
                  border: '1px solid #d1d5db',
                  background: '#f9fafb',
                  color: '#4b5563',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <span>⟳</span> Scan
              </button>
            </div>
          </div>
          
          <div style={{ 
            marginTop: '8px', 
            color: '#6b7280', 
            fontSize: '0.85em',
            fontStyle: 'italic'
          }}>
            Uses NetworkManager (nmcli) if available, falls back to wpa_cli.
          </div>
        </div>
      </div>
    </div>
  )
}

export default WiFiPage
