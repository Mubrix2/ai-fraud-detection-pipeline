// frontend/src/App.jsx
import { useState, useEffect, useCallback } from 'react'
import { getRecentTransactions, getStats, checkHealth } from './api/client'
import StatsBar             from './components/StatsBar'
import SubmitForm           from './components/SubmitForm'
import TransactionTable     from './components/TransactionTable'
import ShapModal            from './components/ShapModal'
import InvestigationPanel   from './components/InvestigationPanel'
import ErrorBoundary from './components/ErrorBoundary'

const POLL_INTERVAL = 3000

export default function App() {
  const [transactions, setTxns]      = useState([])
  const [stats,        setStats]     = useState(null)
  const [selected,     setSelected]  = useState(null)
  const [healthy,      setHealthy]   = useState(null)
  const [lastUpdate,   setLastUpdate] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [recent, s] = await Promise.all([
        getRecentTransactions(100),
        getStats(),
      ])
      setTxns(recent.transactions || [])
      setStats(s)
      setLastUpdate(new Date())
      setHealthy(true)
    } catch {
      setHealthy(false)
    }
  }, [])

  useEffect(() => {
    checkHealth().then(() => setHealthy(true)).catch(() => setHealthy(false))
    refresh()
  }, [refresh])

  useEffect(() => {
    const id = setInterval(refresh, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [refresh])

  // Keep selected transaction in sync with latest data
  useEffect(() => {
    if (selected) {
      const updated = transactions.find(
        t => t.transaction_id === selected.transaction_id
      )
      if (updated) setSelected(updated)
    }
  }, [transactions])

  return (
    <div className="min-h-screen bg-gray-50">

      {/* SHAP Modal */}
      {selected && (
        <ShapModal
          transaction={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-screen-xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-lg font-bold text-gray-900">
              Fraud Detection Dashboard
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Real-time · XGBoost + Isolation Forest · AML · SHAP
            </p>
          </div>
          <div className="flex items-center gap-3">
            {lastUpdate && (
              <span className="text-xs text-gray-400">
                Updated {lastUpdate.toLocaleTimeString()}
              </span>
            )}
            <span className={`text-xs px-3 py-1 rounded-full flex items-center gap-1.5
              ${healthy === true  ? 'bg-green-50 text-green-700' :
                healthy === false ? 'bg-red-50 text-red-600' :
                'bg-gray-100 text-gray-400'}`}>
              <span className={`w-1.5 h-1.5 rounded-full
                ${healthy === true ? 'bg-green-500 animate-pulse' :
                  healthy === false ? 'bg-red-400' : 'bg-gray-400'}`}/>
              {healthy === true ? 'API Connected' :
               healthy === false ? 'API Unreachable' : 'Connecting…'}
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-screen-xl mx-auto px-6 py-6">
        <StatsBar stats={stats} />
        <SubmitForm onSubmitted={refresh} />

        <div className="flex justify-between items-center mb-3">
          <h2 className="font-semibold text-gray-700">
            Recent Transactions
            <span className="ml-2 text-sm font-normal text-gray-400">
              ({transactions.length})
            </span>
          </h2>
          <span className="text-xs text-gray-400">
            Click a row to see SHAP explanation
          </span>
        </div>

        <TransactionTable
          transactions={transactions}
          selected={selected}
          onSelect={setSelected}
        />

        <InvestigationPanel />
      </main>
    </div>
  )
}