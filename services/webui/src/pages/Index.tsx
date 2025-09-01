import React, { useEffect, useRef, useState } from 'react'
import { getReading, getConfig, tare, zero, updateDisplayUnit, getPreferences, updatePreferences } from '../lib/api'

type R = { grams: number; ts: string; stable: boolean }

const IndexPage: React.FC = () => {
  const [reading, setReading] = useState<R | null>(null)
  const [status, setStatus] = useState<string>('connecting...')
  const [maxCap, setMaxCap] = useState<number>(0)
  const [unit, setUnit] = useState<'g' | 'kg'>('g')
  const [displayUnit, setDisplayUnit] = useState<'g' | 'kg'>('g')
  const reconnectTimeoutRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 10;

  const connectWebSocket = () => {
    // Clear any existing reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close existing WebSocket if any
    if (wsRef.current) {
      try {
        wsRef.current.onclose = null; // Remove handler to prevent reconnection
        wsRef.current.close();
      } catch (e) {
        console.error('Error closing existing WebSocket:', e);
      }
      wsRef.current = null;
    }

    const wsUrl = (() => {
      // Use REACT_APP_WS_HOST from environment if available, otherwise use current host
      const host = (window as any).REACT_APP_WS_HOST || window.location.host;
      // Default to wss if on HTTPS, otherwise use ws
      const isSecure = window.location.protocol === 'https:';
      const proto = isSecure ? 'wss' : 'ws';
      // Ensure we don't have double slashes in the URL
      const cleanHost = host.replace(/^https?:\/\//, '').replace(/\/$/, '');
      return `${proto}://${cleanHost}/ws/weight`;
    })();

    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);
    
    let pingInterval: number | null = null;
    let lastPongTime = Date.now();
    const PING_INTERVAL = 30000; // 30 seconds
    const PONG_TIMEOUT = 10000;  // 10 seconds
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setStatus('live');
      reconnectAttemptsRef.current = 0; // Reset attempts on successful connection
      lastPongTime = Date.now();
      
      // Start ping-pong
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send('ping');
            
            // Check if we got a pong recently
            if (Date.now() - lastPongTime > PONG_TIMEOUT) {
              console.warn('No pong received, reconnecting...');
              ws.close(); // This will trigger onclose and reconnect
            }
          } catch (e) {
            console.error('Error sending ping:', e);
            ws.close();
          }
        }
      }, PING_INTERVAL);
    };
    
    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      setStatus('disconnected');
      
      // Clean up ping interval
      if (pingInterval !== null) {
        window.clearInterval(pingInterval);
        pingInterval = null;
      }
      
      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        console.error('Max reconnection attempts reached');
        return;
      }
      
      // Exponential backoff with jitter
      const baseDelay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
      const jitter = Math.random() * 1000; // Add up to 1s jitter
      const delay = Math.min(baseDelay + jitter, 30000); // Max 30s delay
      
      reconnectAttemptsRef.current++;
      console.log(`Reconnecting (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}) in ${Math.round(delay)}ms...`);
      
      // Clear any existing timeout first
      if (reconnectTimeoutRef.current !== null) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectWebSocket();
      }, delay) as unknown as number; // Type assertion for browser environment
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      // The close handler will be called after an error
    };
    
    ws.onmessage = (ev) => {
      try {
        // Handle pong messages
        if (ev.data === 'pong') {
          lastPongTime = Date.now();
          return;
        }
        
        // Handle handshake
        if (typeof ev.data === 'string') {
          try {
            const message = JSON.parse(ev.data);
            if (message.type === 'handshake' && message.status === 'connected') {
              console.log('WebSocket handshake successful');
              return;
            }
          } catch (e) {
            // Not a JSON message, continue to normal processing
          }
        }
        
        // Handle weight data
        const data = JSON.parse(ev.data) as R;
        setReading(data);
      } catch (e) {
        console.error('Error processing WebSocket message:', e);
      }
    };
    
    wsRef.current = ws;
  };

  // Handle unit changes and save to preferences
  const onUnitChange = async (newUnit: 'g' | 'kg') => {
    setUnit(newUnit);
    setDisplayUnit(newUnit);
    try {
      await updatePreferences({ unit: newUnit });
    } catch (e) {
      console.error('Failed to save preferences:', e);
    }
  };

  useEffect(() => {
    // Load initial data
    (async () => {
      try {
        setReading(await getReading());
        const prefs = await getPreferences();
        // Ensure the unit is either 'g' or 'kg'
        const validUnit = prefs?.unit === 'kg' ? 'kg' : 'g';
        setUnit(validUnit);
        setDisplayUnit(validUnit);
      } catch (e) {
        console.error('Failed to load config or preferences:', e);
      }
    })();

    // Setup WebSocket connection
    connectWebSocket();
    
    // Cleanup function
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null; // Disable onclose handler to prevent reconnection
        wsRef.current.close();
        wsRef.current = null;
      }
      
      if (reconnectTimeoutRef.current !== null) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      reconnectAttemptsRef.current = 0; // Reset reconnection attempts
    };
  }, []);

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

  // Update display unit when unit changes
  useEffect(() => {
    if (unit !== displayUnit) {
      const updateUnit = async () => {
        try {
          // Only update the display unit, preferences are now handled by onUnitChange
          await Promise.all([
            updateDisplayUnit(unit),
            updatePreferences({ unit })
          ]);
          setDisplayUnit(unit);
        } catch (error) {
          console.error('Failed to update display unit:', error);
          // Revert to previous unit on error
          setUnit(displayUnit);
        }
      };
      updateUnit();
    }
  }, [unit, displayUnit])

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
              padding: 4
            }}>
              <button
                onClick={() => onUnitChange('g')}
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
                onClick={() => onUnitChange('kg')}
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
