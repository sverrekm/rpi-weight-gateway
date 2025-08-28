import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const NavLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => {
  const loc = useLocation()
  const active = loc.pathname === to
  return (
    <Link to={to} style={{
      padding: '8px 12px',
      borderRadius: 6,
      textDecoration: 'none',
      color: active ? '#fff' : '#111',
      background: active ? '#2563eb' : 'transparent',
      border: '1px solid #e5e7eb',
      marginRight: 8,
    }}>{children}</Link>
  )
}

const App: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', color: '#111', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottom: '1px solid #e5e7eb', background: '#fff', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ fontWeight: 700 }}>rpi-weight-gateway</div>
        <nav>
          <NavLink to="/">Live</NavLink>
          <NavLink to="/calibrate">Calibrate</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
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
