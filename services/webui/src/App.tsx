import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const NavButton: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => {
  const loc = useLocation()
  const active = loc.pathname === to
  return (
    <Link to={to} style={{
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
      boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
    }}>{children}</Link>
  )
}

const App: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', color: '#111', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, borderBottom: '1px solid #e5e7eb', background: '#fff', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ fontWeight: 700, fontSize: 18, marginRight: 16 }}>rpi-weight-gateway</div>
          <nav style={{ display: 'flex', gap: 8 }}>
            <NavButton to="/">Live Weight</NavButton>
            <NavButton to="/calibrate">Calibrate</NavButton>
            <NavButton to="/settings">Settings</NavButton>
            <NavButton to="/wifi">Wi‑Fi</NavButton>
          </nav>
        </div>
      </header>
      <main style={{ maxWidth: 960, margin: '0 auto', padding: 16 }}>{children}</main>
      <footer style={{ textAlign: 'center', padding: 16, color: '#6b7280' }}>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, alignItems: 'center' }}>
          <img src="/static/logo.png" alt="logo" style={{ height: 18 }} onError={(e:any)=>{ e.currentTarget.style.display='none' }} />
          <span>© 2025 rpi-weight-gateway</span>
        </div>
      </footer>
    </div>
  )
}

export default App
