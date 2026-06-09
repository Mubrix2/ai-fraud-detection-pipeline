// frontend/src/components/ShapModal.jsx
import { useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  Cell, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import DecisionBadge from './DecisionBadge'

export default function ShapModal({ transaction: tx, onClose }) {
  if (!tx) return null

  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', fn)
    return () => window.removeEventListener('keydown', fn)
  }, [onClose])

  const isAuto    = tx.note?.includes('Auto-approved')
  const chartData = (tx.top_reasons || [])
  .filter(r => r && r.description && typeof r.shap_value === 'number')
  .map(r => ({
    name: (r.description || '').length > 32
      ? r.description.slice(0, 32) + '…'
      : r.description,
    value:     r.shap_value,
    direction: r.direction || 'increased_risk',
  }))

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm
        flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl
        max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex justify-between items-start p-5
          border-b border-gray-100 sticky top-0 bg-white">
          <div>
            <h2 className="font-bold text-gray-900">Transaction Assessment</h2>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              {tx.transaction_id}
            </p>
          </div>
          <button onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl
              w-8 h-8 flex items-center justify-center
              rounded-lg hover:bg-gray-100">✕</button>
        </div>

        <div className="p-5">
          {/* Auto-approve banner */}
          {isAuto && (
            <div className="mb-4 px-3 py-2 bg-blue-50 border
              border-blue-200 rounded text-xs text-blue-700">
              <strong>Auto-approved</strong> — {tx.transaction?.type} is
              outside the model's training scope.
            </div>
          )}

          {/* Summary grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {[
              ['Decision',         <DecisionBadge decision={tx.decision} />],
              ['Fraud Probability', isAuto ? '—'
                : <span className={`font-bold text-xl ${
                    tx.fraud_probability > 0.85 ? 'text-red-600' :
                    tx.fraud_probability > 0.60 ? 'text-yellow-600' :
                    'text-green-600'}`}>
                    {(tx.fraud_probability * 100).toFixed(1)}%
                  </span>],
              ['Anomaly',          tx.anomaly_label || '—'],
              ['Amount',           `₦${Number(tx.transaction?.amount || 0).toLocaleString()}`],
              ['Type',             tx.transaction?.type || '—'],
              ['AML Flags',        tx.aml_flag_count || 0],
              ['SAR Required',     tx.requires_sar ? '⚠ Yes' : 'No'],
              ['Processing',       `${tx.processing_ms?.toFixed(1) || '—'} ms`],
            ].map(([label, val]) => (
              <div key={label} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <div className="text-sm font-semibold">{val}</div>
              </div>
            ))}
          </div>

          {/* Rules triggered */}
          {tx.triggered_rules?.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-medium text-gray-600 mb-2">
                Business Rules Triggered
              </p>
              <div className="space-y-1">
                {tx.triggered_rules.map((r, i) => (
                  <div key={i}
                    className="text-xs bg-orange-50 border border-orange-200
                      text-orange-800 rounded px-3 py-1.5">
                    ⚡ {r}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SHAP chart */}
          {!isAuto && chartData.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-medium text-gray-600 mb-2">
                SHAP Feature Contributions
              </p>
              <div className="bg-gray-50 rounded-lg p-3">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={chartData} layout="vertical"
                    margin={{ top: 4, right: 20, bottom: 4, left: 8 }}>
                    <XAxis type="number" tick={{ fontSize: 10 }}
                      tickFormatter={v => v.toFixed(2)} />
                    <YAxis type="category" dataKey="name"
                      tick={{ fontSize: 10 }} width={185} />
                    <ReferenceLine x={0} stroke="#d1d5db" />
                    <Tooltip
                      formatter={(v, _, p) => [
                        `${v.toFixed(4)} (${p.payload.direction === 'increased_risk'
                          ? '↑ increases risk' : '↓ decreases risk'})`,
                        'SHAP'
                      ]}
                      contentStyle={{ fontSize: 11 }}
                    />
                    <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                      {chartData.map((e, i) => (
                        <Cell key={i}
                          fill={e.direction === 'increased_risk'
                            ? '#ef4444' : '#22c55e'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex gap-4 justify-center mt-1 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-red-500 inline-block"/>
                    Increases fraud risk
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-green-500 inline-block"/>
                    Decreases fraud risk
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Explanation text */}
          {tx.explanation_text && (
            <div className="mb-4">
              <p className="text-xs font-medium text-gray-600 mb-2">
                Compliance Explanation
              </p>
              <div className="bg-amber-50 border border-amber-200
                rounded-lg p-3 text-xs text-amber-800 whitespace-pre-line">
                {tx.explanation_text}
              </div>
            </div>
          )}

          {/* AML note */}
          {tx.aml_note && tx.aml_flag_count > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-2">
                AML Assessment
              </p>
              <div className="bg-orange-50 border border-orange-200
                rounded-lg p-3 text-xs text-orange-800 whitespace-pre-line">
                {tx.aml_note}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}