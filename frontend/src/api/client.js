// frontend/src/api/client.js
const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const submitTransaction   = (data) =>
  request('/api/v1/transactions/submit', { method: 'POST', body: JSON.stringify(data) })

export const getResult           = (id) =>
  request(`/api/v1/transactions/results/${id}`)

export const getRecentTransactions = (limit = 100) =>
  request(`/api/v1/transactions/recent?limit=${limit}`)

export const getStats            = () =>
  request('/api/v1/transactions/stats')

export const investigate         = (question, sessionId = 'analyst-1') =>
  request('/api/v1/transactions/investigate', {
    method: 'POST',
    body: JSON.stringify({ question, session_id: sessionId }),
  })

export const checkHealth         = () =>
  request('/health')