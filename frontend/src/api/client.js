// frontend/src/api/client.js
//
// DEPLOYMENT MODES:
//
// Docker Compose (local):
//   VITE_API_URL is not set → BASE = ''
//   fetch('/api/v1/...') → Vite proxy (dev) or nginx proxy (Docker)
//   No localhost anywhere in the request.
//
// Vercel + Render (cloud):
//   VITE_API_URL = 'https://fraud-detection-api.onrender.com'
//   fetch('https://fraud-detection-api.onrender.com/api/v1/...')
//   Set this in Vercel dashboard → Environment Variables.
//   Never hardcode it here.

const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const submitTransaction     = (data) =>
  request('/api/v1/transactions/submit', {
    method: 'POST', body: JSON.stringify(data),
  })

export const getResult             = (id) =>
  request(`/api/v1/transactions/results/${id}`)

export const getRecentTransactions = (limit = 100) =>
  request(`/api/v1/transactions/recent?limit=${limit}`)

export const getStats              = () =>
  request('/api/v1/transactions/stats')

export const investigate           = (question, sessionId = 'analyst-1') =>
  request('/api/v1/transactions/investigate', {
    method: 'POST',
    body: JSON.stringify({ question, session_id: sessionId }),
  })

export const checkHealth           = () =>
  request('/health')