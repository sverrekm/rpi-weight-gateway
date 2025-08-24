import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom'
import App from './App'
import IndexPage from './pages/Index'
import SettingsPage from './pages/Settings'
import CalibratePage from './pages/Calibrate'

const Root = () => (
  <BrowserRouter>
    <App>
      <Routes>
        <Route path="/" element={<IndexPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/calibrate" element={<CalibratePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </App>
  </BrowserRouter>
)

createRoot(document.getElementById('root')!).render(<Root />)
