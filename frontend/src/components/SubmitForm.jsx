// frontend/src/components/SubmitForm.jsx
import { useState } from 'react'
import { submitTransaction } from '../api/client'

const SUSPICIOUS = {
  transaction_id: `TXN-SUSPICIOUS-${Date.now()}`,
  step: 3, type: 'TRANSFER', amount: 750000,
  name_orig: 'C1234567890', oldbalance_org: 750000, newbalance_orig: 0,
  name_dest: 'C9876543210', oldbalance_dest: 0, newbalance_dest: 0,
}

const LEGITIMATE = {
  transaction_id: `TXN-LEGIT-${Date.now()}`,
  step: 14, type: 'PAYMENT', amount: 25000,
  name_orig: 'C1111111111', oldbalance_org: 500000, newbalance_orig: 475000,
  name_dest: 'M2222222222', oldbalance_dest: 1000000, newbalance_dest: 1025000,
}

const TYPES = ['TRANSFER', 'CASH_OUT', 'PAYMENT', 'CASH_IN', 'DEBIT']

export default function SubmitForm({ onSubmitted }) {
  const [form, setForm]         = useState(SUSPICIOUS)
  const [submitting, setSubmit] = useState(false)
  const [lastTxn, setLastTxn]   = useState(null)
  const [error, setError]       = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const loadPreset = (preset) => {
    setForm({ ...preset, transaction_id: `TXN-${Date.now()}` })
    setError(null)
    setLastTxn(null)
  }

  const submit = async () => {
    setSubmit(true)
    setError(null)
    try {
      const resp = await submitTransaction(form)
      setLastTxn(resp.transaction_id)
      onSubmitted?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmit(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <h2 className="font-semibold text-gray-800 mb-3">Submit Transaction</h2>

      {/* Presets */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => loadPreset(SUSPICIOUS)}
          className="px-3 py-1 text-xs bg-red-50 text-red-700
            border border-red-200 rounded hover:bg-red-100">
          🚨 Suspicious — Account drain
        </button>
        <button onClick={() => loadPreset(LEGITIMATE)}
          className="px-3 py-1 text-xs bg-green-50 text-green-700
            border border-green-200 rounded hover:bg-green-100">
          ✅ Legitimate — Normal payment
        </button>
      </div>

      {/* Form fields */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        {[
          ['Transaction ID', 'transaction_id', 'text'],
          ['Amount (₦)',     'amount',          'number'],
          ['Step (hour)',    'step',            'number'],
          ['Sender Balance Before', 'oldbalance_org', 'number'],
          ['Sender Balance After',  'newbalance_orig', 'number'],
          ['Recipient Balance Before', 'oldbalance_dest', 'number'],
          ['Recipient Balance After',  'newbalance_dest', 'number'],
        ].map(([label, key, type]) => (
          <div key={key}>
            <label className="text-xs text-gray-500 mb-0.5 block">{label}</label>
            <input
              type={type}
              value={form[key] ?? ''}
              onChange={e => set(key, type === 'number'
                ? parseFloat(e.target.value) || 0
                : e.target.value)}
              className="w-full text-sm border border-gray-200 rounded
                px-2 py-1.5 focus:outline-none focus:border-blue-400"
            />
          </div>
        ))}

        <div>
          <label className="text-xs text-gray-500 mb-0.5 block">Type</label>
          <select
            value={form.type}
            onChange={e => set('type', e.target.value)}
            className="w-full text-sm border border-gray-200 rounded
              px-2 py-1.5 focus:outline-none focus:border-blue-400">
            {TYPES.map(t => <option key={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {/* Submit */}
      <div className="flex items-center gap-3">
        <button
          onClick={submit}
          disabled={submitting}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium
            rounded hover:bg-blue-700 disabled:opacity-50">
          {submitting ? 'Submitting...' : 'Submit Transaction'}
        </button>
        {lastTxn && (
          <span className="text-xs text-green-600">
            ✓ Submitted {lastTxn.slice(0, 24)}
          </span>
        )}
        {error && (
          <span className="text-xs text-red-600">Error: {error}</span>
        )}
      </div>
    </div>
  )
}