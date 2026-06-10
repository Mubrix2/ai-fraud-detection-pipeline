// frontend/src/components/ShapModal.jsx
import { useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  Cell, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import DecisionBadge from './DecisionBadge'

export default function ShapModal({ transaction: tx, onClose }) {
  // Guard — render nothing if no transaction selected
  if (!tx) return null

  // Close on Escape key
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', fn)
    return () => window.removeEventListener('keydown', fn)
  }, [onClose])

  // ── Safe data extraction ────────────────────────────────────────────────────
  // Every field uses a fallback — BLOCKED transactions have different
  // data shapes than APPROVED ones and missing fields must not crash

  const decision       = tx.decision       || 'UNKNOWN'
  const fraudProb      = typeof tx.fraud_probability === 'number'
                         ? tx.fraud_probability : null
  const riskLevel      = tx.risk_level     || '—'
  const anomalyLabel   = tx.anomaly_label  || '—'
  const processingMs   = typeof tx.processing_ms === 'number'
                         ? tx.processing_ms.toFixed(1) : '—'
  const amlFlagCount   = tx.aml_flag_count || 0
  const requiresSar    = tx.requires_sar   || false
  const requiresCtr    = tx.requires_ctr   || false
  const triggeredRules = Array.isArray(tx.triggered_rules)
                         ? tx.triggered_rules : []
  const topReasons     = Array.isArray(tx.top_reasons)
                         ? tx.top_reasons : []
  const explainText    = tx.explanation_text || ''
  const amlNote        = tx.aml_note || ''
  const isAutoApproved = typeof tx.note === 'string' &&
                         tx.note.includes('Auto-approved')
  const txType         = tx.transaction?.type   || '—'
  const txAmount       = typeof tx.transaction?.amount === 'number'
                         ? tx.transaction.amount : 0

  // ── SHAP chart data ─────────────────────────────────────────────────────────
  // Filter and validate every field before passing to Recharts
  // Recharts crashes on null, undefined, NaN, or Infinity values
  const chartData = topReasons
    .filter(r => {
      if (!r) return false
      if (typeof r.description !== 'string') return false
      if (typeof r.shap_value !== 'number') return false
      if (!isFinite(r.shap_value)) return false  // reject NaN and Infinity
      return true
    })
    .map(r => ({
      name:      r.description.length > 30
                 ? r.description.slice(0, 30) + '…'
                 : r.description,
      value:     r.shap_value,
      direction: typeof r.direction === 'string'
                 ? r.direction : 'increased_risk',
    }))

  // ── Colour helpers ──────────────────────────────────────────────────────────
  const probColour =
    fraudProb === null  ? 'text-gray-500' :
    fraudProb >= 0.85   ? 'text-red-600 font-bold' :
    fraudProb >= 0.60   ? 'text-yellow-600 font-semibold' :
    'text-green-600 font-semibold'

  const probDisplay = fraudProb === null
    ? '—'
    : `${(fraudProb * 100).toFixed(1)}%`

  // ── Custom Recharts tooltip ─────────────────────────────────────────────────
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null
    const item = payload[0]?.payload
    if (!item) return null
    return (
      <div className="bg-white border border-gray-200 rounded-lg
        shadow-lg p-3 text-xs max-w-[220px]">
        <p className="font-medium text-gray-800 mb-1 break-words">
          {item.name}
        </p>
        <p className={item.direction === 'increased_risk'
          ? 'text-red-600' : 'text-green-600'}>
          {item.direction === 'increased_risk'
            ? '▲ Increases fraud risk'
            : '▼ Decreases fraud risk'}
        </p>
        <p className="text-gray-500 mt-1">
          SHAP: {typeof item.value === 'number'
            ? item.value.toFixed(4) : '—'}
        </p>
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm
        flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}>

      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl
        max-h-[90vh] overflow-y-auto">

        {/* ── Header ─────────────────────────────────────────────────── */}
        <div className="flex justify-between items-start p-5
          border-b border-gray-100 sticky top-0 bg-white z-10">
          <div>
            <h2 className="font-bold text-gray-900">
              Transaction Assessment
            </h2>
            <p className="text-xs text-gray-400 font-mono mt-0.5 break-all">
              {tx.transaction_id || 'Unknown ID'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-xl
              w-8 h-8 flex items-center justify-center
              rounded-lg hover:bg-gray-100 transition-colors flex-shrink-0">
            ✕
          </button>
        </div>

        <div className="p-5 space-y-5">

          {/* ── Auto-approved banner ────────────────────────────────── */}
          {isAutoApproved && (
            <div className="px-3 py-2 bg-blue-50 border border-blue-200
              rounded-lg text-xs text-blue-700">
              <strong>Auto-approved</strong> — {txType} transactions are
              outside the model's training scope. No ML scoring applied.
            </div>
          )}

          {/* ── Summary grid ────────────────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Decision</p>
              <DecisionBadge decision={decision} />
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Fraud Probability</p>
              <p className={`text-xl mt-0.5 ${probColour}`}>
                {isAutoApproved ? '—' : probDisplay}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Risk Level</p>
              <p className="text-sm font-semibold mt-0.5">{riskLevel}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Anomaly</p>
              <p className="text-sm font-semibold mt-0.5">{anomalyLabel}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Amount</p>
              <p className="text-sm font-semibold mt-0.5">
                ₦{txAmount.toLocaleString()}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Type</p>
              <p className="text-sm font-semibold mt-0.5">{txType}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">AML Flags</p>
              <p className={`text-sm font-semibold mt-0.5 ${
                amlFlagCount > 0 ? 'text-orange-600' : 'text-gray-700'
              }`}>
                {amlFlagCount > 0 ? `⚠ ${amlFlagCount}` : 'None'}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Processing</p>
              <p className="text-sm font-semibold mt-0.5">
                {processingMs} ms
              </p>
            </div>
          </div>

          {/* ── SAR / CTR badges ────────────────────────────────────── */}
          {(requiresSar || requiresCtr) && (
            <div className="flex gap-2 flex-wrap">
              {requiresSar && (
                <span className="text-xs px-3 py-1 bg-red-100
                  text-red-800 rounded-full border border-red-300
                  font-semibold">
                  ⚠ SAR Required — File with NFIU within 24h
                </span>
              )}
              {requiresCtr && (
                <span className="text-xs px-3 py-1 bg-orange-100
                  text-orange-800 rounded-full border border-orange-300
                  font-semibold">
                  ⚠ CTR Required — Mandatory NFIU report
                </span>
              )}
            </div>
          )}

          {/* ── Rules triggered ─────────────────────────────────────── */}
          {triggeredRules.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-2">
                Business Rules Triggered
              </p>
              <div className="space-y-1">
                {triggeredRules.map((rule, i) => (
                  <div key={i}
                    className="text-xs bg-orange-50 border border-orange-200
                      text-orange-800 rounded px-3 py-1.5">
                    ⚡ {String(rule)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── SHAP chart ───────────────────────────────────────────── */}
          {!isAutoApproved && chartData.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-2">
                SHAP Feature Contributions
                <span className="ml-2 font-normal text-gray-400">
                  (why the model gave this score)
                </span>
              </p>
              <div className="bg-gray-50 rounded-lg p-4">
                <ResponsiveContainer width="100%" height={chartData.length * 44 + 20}>
                  <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10 }}
                      tickFormatter={v => v.toFixed(2)}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 10 }}
                      width={190}
                    />
                    <ReferenceLine x={0} stroke="#d1d5db" strokeWidth={1} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" radius={[0, 3, 3, 0]} maxBarSize={20}>
                      {chartData.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={entry.direction === 'increased_risk'
                            ? '#ef4444' : '#22c55e'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex gap-5 justify-center mt-2
                  text-xs text-gray-500">
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded bg-red-500 inline-block"/>
                    Increases fraud risk
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded bg-green-500 inline-block"/>
                    Decreases fraud risk
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* No SHAP data message */}
          {!isAutoApproved && chartData.length === 0 && (
            <div className="text-xs text-gray-400 italic text-center py-4">
              SHAP explanation not available for this transaction.
            </div>
          )}

          {/* ── Compliance explanation ───────────────────────────────── */}
          {explainText && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-2">
                Compliance Explanation
              </p>
              <div className="bg-amber-50 border border-amber-200
                rounded-lg p-3 text-xs text-amber-800 whitespace-pre-line
                leading-relaxed">
                {explainText}
              </div>
            </div>
          )}

          {/* ── AML note ────────────────────────────────────────────── */}
          {amlFlagCount > 0 && amlNote && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-2">
                AML Assessment
              </p>
              <div className="bg-orange-50 border border-orange-200
                rounded-lg p-3 text-xs text-orange-800 whitespace-pre-line
                leading-relaxed">
                {amlNote}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}