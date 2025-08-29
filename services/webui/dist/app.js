// Simple React app for RPi Weight Gateway
const { useState, useEffect, useRef } = React;
const { BrowserRouter, Routes, Route, Link, useLocation, Navigate } = ReactRouterDOM;

// API functions
const api = {
  async getReading() {
    const r = await fetch('/api/reading');
    if (!r.ok) throw new Error('reading failed');
    return r.json();
  },
  async getConfig() {
    const r = await fetch('/api/config');
    if (!r.ok) throw new Error('config failed');
    return r.json();
  },
  async saveConfig(cfg) {
    const r = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
    if (!r.ok) throw new Error('save failed');
    return r.json();
  },
  async tare() {
    await fetch('/api/tare', { method: 'POST' });
  },
  async zero() {
    await fetch('/api/zero', { method: 'POST' });
  },
  async calibrate(known_grams) {
    const r = await fetch('/api/calibrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ known_grams }),
    });
    if (!r.ok) throw new Error('calibrate failed');
    return r.json();
  },
  async getWifiStatus() {
    const r = await fetch('/api/wifi/status');
    if (!r.ok) throw new Error('wifi status failed');
    return r.json();
  },
  async scanWifi() {
    const r = await fetch('/api/wifi/scan');
    if (!r.ok) throw new Error('wifi scan failed');
    return r.json();
  },
  async connectWifi(ssid, psk) {
    const r = await fetch('/api/wifi/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid, psk })
    });
    return r.json();
  }
};

// Navigation component
function NavButton({ to, children }) {
  const loc = useLocation();
  const active = loc.pathname === to;
  return React.createElement(Link, {
    to: to,
    style: {
      padding: '10px 16px',
      borderRadius: 8,
      textDecoration: 'none',
      color: active ? '#fff' : '#374151',
      background: active ? '#2563eb' : '#f9fafb',
      border: active ? '1px solid #2563eb' : '1px solid #d1d5db',
      fontWeight: active ? 600 : 500,
      fontSize: 14,
      display: 'inline-block',
      transition: 'all 0.2s',
      boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
    }
  }, children);
}

// Index page component
function IndexPage() {
  const [reading, setReading] = useState(null);
  const [status, setStatus] = useState('connecting...');
  const [maxCap, setMaxCap] = useState(0);
  const wsRef = useRef(null);

  useEffect(() => {
    // Load configuration for max capacity
    (async () => {
      try {
        const cfg = await api.getConfig();
        setMaxCap(cfg.max_capacity_g || 0);
      } catch {}
    })();

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${proto}://${location.host}/ws/weight`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => setStatus('live');
    ws.onclose = () => setStatus('disconnected');
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      setReading(data);
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    // Fallback poll if WS not working
    let t;
    if (!reading) {
      t = setInterval(async () => {
        try { setReading(await api.getReading()); } catch {}
      }, 1000);
    }
    return () => clearInterval(t);
  }, []);

  const grams = reading ? reading.grams.toFixed(2) : '---';
  const stable = reading?.stable;
  const overCap = !!reading && maxCap > 0 && reading.grams > maxCap;

  return React.createElement('div', {
    style: { textAlign: 'center', maxWidth: 600, margin: '0 auto' }
  }, [
    overCap && React.createElement('div', {
      key: 'warning',
      style: { background: '#fee2e2', color: '#991b1b', padding: '12px 16px', border: '1px solid #fecaca', borderRadius: 8, marginBottom: 24, textAlign: 'left' }
    }, `⚠️ Over capacity: ${reading.grams.toFixed(2)} g exceeds ${maxCap} g`),
    
    React.createElement('div', {
      key: 'main',
      style: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 32, marginBottom: 24 }
    }, [
      React.createElement('div', {
        key: 'weight',
        style: { fontSize: 72, fontWeight: 800, letterSpacing: -2, margin: '0 0 8px 0', color: stable ? '#059669' : '#6b7280' }
      }, `${grams} g`),
      React.createElement('div', {
        key: 'status-text',
        style: { fontSize: 18, color: '#6b7280', marginBottom: 24 }
      }, stable ? '✅ Stable' : '⏳ Measuring...'),
      
      React.createElement('div', {
        key: 'buttons',
        style: { display: 'flex', gap: 12, justifyContent: 'center' }
      }, [
        React.createElement('button', {
          key: 'tare',
          onClick: () => api.tare(),
          style: { padding: '12px 24px', fontSize: 16, fontWeight: 600, background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }
        }, 'Tare'),
        React.createElement('button', {
          key: 'zero',
          onClick: () => api.zero(),
          style: { padding: '12px 24px', fontSize: 16, fontWeight: 600, background: '#dc2626', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }
        }, 'Zero')
      ])
    ]),
    
    React.createElement('div', {
      key: 'connection',
      style: { color: '#6b7280', fontSize: 14 }
    }, [
      'Connection: ',
      React.createElement('span', {
        key: 'status-span',
        style: { color: status === 'live' ? '#059669' : '#dc2626', fontWeight: 600 }
      }, status)
    ])
  ]);
}

// WiFi page component
function WiFiPage() {
  const [status, setStatus] = useState(null);
  const [nets, setNets] = useState([]);
  const [selected, setSelected] = useState('');
  const [psk, setPsk] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try { setStatus(await api.getWifiStatus()); } catch {}
  };
  const scan = async () => {
    setMsg('Scanning...');
    try { const r = await api.scanWifi(); setNets(r.networks || []); setMsg(''); } catch { setMsg('Scan failed'); }
  };

  useEffect(() => { refresh(); scan(); }, []);

  const onConnect = async () => {
    if (!selected) { setMsg('Select SSID'); return; }
    setLoading(true); setMsg('Connecting...');
    try {
      const r = await api.connectWifi(selected, psk);
      if (r.error) { setMsg('Error: ' + r.error); }
      else { setMsg('Connected ✓'); await refresh(); }
    } catch (e) { setMsg('Error: ' + (e.message || 'failed')); }
    finally { setLoading(false); }
  };

  return React.createElement('div', {}, [
    React.createElement('h2', { key: 'title' }, 'Wi‑Fi'),
    React.createElement('div', {
      key: 'content',
      style: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }
    }, [
      React.createElement('div', {
        key: 'status',
        style: { marginBottom: 8, color: '#6b7280' }
      }, `Status: ${status ? (status.connected ? `connected to ${status.ssid} (${status.ip||'-'})` : 'disconnected') : '—'}`),
      React.createElement('div', {
        key: 'controls',
        style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }
      }, [
        React.createElement('select', {
          key: 'select',
          value: selected,
          onChange: e => setSelected(e.target.value)
        }, [
          React.createElement('option', { key: 'empty', value: '' }, 'Select SSID'),
          ...nets.map((n, i) => React.createElement('option', { key: i, value: n.ssid }, `${n.ssid} ${typeof n.signal==='number' ? `(${n.signal}%)` : ''}`))
        ]),
        React.createElement('input', {
          key: 'password',
          type: 'password',
          value: psk,
          onChange: e => setPsk(e.target.value),
          placeholder: 'Password (leave empty if open)'
        }),
        React.createElement('button', {
          key: 'connect',
          onClick: onConnect,
          disabled: loading
        }, loading ? 'Connecting...' : 'Connect'),
        React.createElement('button', {
          key: 'rescan',
          onClick: scan,
          disabled: loading
        }, 'Rescan')
      ]),
      React.createElement('div', {
        key: 'message',
        style: { marginTop: 8, color: msg.startsWith('Error') ? '#dc2626' : '#16a34a' }
      }, msg)
    ]),
    React.createElement('div', {
      key: 'note',
      style: { marginTop: 16, color: '#6b7280' }
    }, 'Uses nmcli if available, falls back to wpa_cli.')
  ]);
}

// Settings page (simplified)
function SettingsPage() {
  return React.createElement('div', {}, [
    React.createElement('h2', { key: 'title' }, 'Settings'),
    React.createElement('p', { key: 'content' }, 'Configuration interface - implementation needed')
  ]);
}

// Calibrate page (simplified)
function CalibratePage() {
  return React.createElement('div', {}, [
    React.createElement('h2', { key: 'title' }, 'Calibrate'),
    React.createElement('p', { key: 'content' }, 'Calibration interface - implementation needed')
  ]);
}

// App component
function App({ children }) {
  return React.createElement('div', {
    style: { fontFamily: 'system-ui, sans-serif', color: '#111', background: '#f8fafc', minHeight: '100vh' }
  }, [
    React.createElement('header', {
      key: 'header',
      style: { display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, borderBottom: '1px solid #e5e7eb', background: '#fff', position: 'sticky', top: 0, zIndex: 10 }
    }, React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', gap: 24 }
    }, [
      React.createElement('div', {
        key: 'brand',
        style: { fontWeight: 700, fontSize: 18, marginRight: 16 }
      }, 'rpi-weight-gateway'),
      React.createElement('nav', {
        key: 'nav',
        style: { display: 'flex', gap: 8 }
      }, [
        React.createElement(NavButton, { key: 'live', to: '/' }, 'Live Weight'),
        React.createElement(NavButton, { key: 'calibrate', to: '/calibrate' }, 'Calibrate'),
        React.createElement(NavButton, { key: 'settings', to: '/settings' }, 'Settings'),
        React.createElement(NavButton, { key: 'wifi', to: '/wifi' }, 'Wi‑Fi')
      ])
    ])),
    React.createElement('main', {
      key: 'main',
      style: { maxWidth: 960, margin: '0 auto', padding: 16 }
    }, children),
    React.createElement('footer', {
      key: 'footer',
      style: { textAlign: 'center', padding: 16, color: '#6b7280' }
    }, React.createElement('div', {
      style: { display: 'flex', justifyContent: 'center', gap: 8, alignItems: 'center' }
    }, [
      React.createElement('img', {
        key: 'logo',
        src: '/static/logo.png',
        alt: 'logo',
        style: { height: 18 },
        onError: e => { e.currentTarget.style.display = 'none'; }
      }),
      React.createElement('span', { key: 'text' }, '© 2025 rpi-weight-gateway')
    ]))
  ]);
}

// Root component
function Root() {
  return React.createElement(BrowserRouter, {}, 
    React.createElement(App, {},
      React.createElement(Routes, {}, [
        React.createElement(Route, { key: 'home', path: '/', element: React.createElement(IndexPage) }),
        React.createElement(Route, { key: 'settings', path: '/settings', element: React.createElement(SettingsPage) }),
        React.createElement(Route, { key: 'calibrate', path: '/calibrate', element: React.createElement(CalibratePage) }),
        React.createElement(Route, { key: 'wifi', path: '/wifi', element: React.createElement(WiFiPage) }),
        React.createElement(Route, { key: 'fallback', path: '*', element: React.createElement(Navigate, { to: '/', replace: true }) })
      ])
    )
  );
}

// Initialize app
ReactDOM.render(React.createElement(Root), document.getElementById('root'));
