// Simple React app for RPi Weight Gateway
const { useState, useEffect, useRef } = React;
const { BrowserRouter, Routes, Route, Link } = ReactRouterDOM;

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
  }
};

// Index page component
function IndexPage() {
  const [reading, setReading] = useState(null);
  const [status, setStatus] = useState('connecting...');
  const wsRef = useRef(null);

  useEffect(() => {
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

  return React.createElement('div', null,
    React.createElement('h2', null, 'Live weight'),
    React.createElement('div', {
      style: { fontSize: 64, fontWeight: 800, letterSpacing: -1, margin: '24px 0' }
    }, `${grams} g ${stable ? '✅' : '...'}`),
    React.createElement('div', { style: { display: 'flex', gap: 8 } },
      React.createElement('button', {
        onClick: () => api.tare(),
        style: { padding: '8px 12px' }
      }, 'Tare'),
      React.createElement('button', {
        onClick: () => api.zero(),
        style: { padding: '8px 12px' }
      }, 'Zero')
    ),
    React.createElement('div', {
      style: { marginTop: 16, color: '#6b7280' }
    }, `Status: ${status}`)
  );
}

// Settings page component
function SettingsPage() {
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(console.error);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.saveConfig(config);
      alert('Settings saved!');
    } catch (err) {
      alert('Failed to save settings');
    }
    setSaving(false);
  };

  if (!config) return React.createElement('div', null, 'Loading...');

  return React.createElement('div', null,
    React.createElement('h2', null, 'Settings'),
    React.createElement('div', { style: { marginBottom: 16 } },
      React.createElement('label', null, 'MQTT Host:'),
      React.createElement('input', {
        type: 'text',
        value: config.mqtt_host || '',
        onChange: (e) => setConfig({...config, mqtt_host: e.target.value}),
        style: { marginLeft: 8, padding: 4 }
      })
    ),
    React.createElement('div', { style: { marginBottom: 16 } },
      React.createElement('label', null, 'MQTT Port:'),
      React.createElement('input', {
        type: 'number',
        value: config.mqtt_port,
        onChange: (e) => setConfig({...config, mqtt_port: parseInt(e.target.value)}),
        style: { marginLeft: 8, padding: 4 }
      })
    ),
    React.createElement('div', { style: { marginBottom: 16 } },
      React.createElement('label', null,
        React.createElement('input', {
          type: 'checkbox',
          checked: config.demo_mode,
          onChange: (e) => setConfig({...config, demo_mode: e.target.checked}),
          style: { marginRight: 8 }
        }),
        'Demo Mode'
      )
    ),
    React.createElement('button', {
      onClick: handleSave,
      disabled: saving,
      style: { padding: '8px 16px' }
    }, saving ? 'Saving...' : 'Save Settings')
  );
}

// Calibrate page component
function CalibratePage() {
  const [knownWeight, setKnownWeight] = useState('100');
  const [calibrating, setCalibrating] = useState(false);
  const [result, setResult] = useState(null);

  const handleCalibrate = async () => {
    setCalibrating(true);
    try {
      const res = await api.calibrate(parseFloat(knownWeight));
      setResult(res);
    } catch (err) {
      alert('Calibration failed');
    }
    setCalibrating(false);
  };

  return React.createElement('div', null,
    React.createElement('h2', null, 'Calibrate'),
    React.createElement('p', null, 'Place a known weight on the scale and enter its value:'),
    React.createElement('div', { style: { marginBottom: 16 } },
      React.createElement('input', {
        type: 'number',
        value: knownWeight,
        onChange: (e) => setKnownWeight(e.target.value),
        style: { padding: 8, marginRight: 8 }
      }),
      React.createElement('span', null, 'grams')
    ),
    React.createElement('button', {
      onClick: handleCalibrate,
      disabled: calibrating,
      style: { padding: '8px 16px' }
    }, calibrating ? 'Calibrating...' : 'Calibrate'),
    result && React.createElement('div', { style: { marginTop: 16, color: 'green' } },
      `Calibration complete! New scale factor: ${result.scale}`
    )
  );
}

// Navigation component
function Navigation() {
  return React.createElement('nav', null,
    React.createElement(Link, { to: '/' }, 'Home'),
    React.createElement(Link, { to: '/settings' }, 'Settings'),
    React.createElement(Link, { to: '/calibrate' }, 'Calibrate')
  );
}

// Main App component
function App() {
  return React.createElement(BrowserRouter, null,
    React.createElement('div', null,
      React.createElement(Navigation),
      React.createElement(Routes, null,
        React.createElement(Route, { path: '/', element: React.createElement(IndexPage) }),
        React.createElement(Route, { path: '/settings', element: React.createElement(SettingsPage) }),
        React.createElement(Route, { path: '/calibrate', element: React.createElement(CalibratePage) })
      )
    )
  );
}

// Render the app
ReactDOM.render(React.createElement(App), document.getElementById('root'));
