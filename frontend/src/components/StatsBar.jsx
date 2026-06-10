// frontend/src/components/StatsBar.jsx
export default function StatsBar({ stats }) {
  const s = stats || {}
  const cards = [
    { label: 'Total Processed', value: s.total_processed ?? 0,
      colour: 'text-blue-700', bg: 'bg-blue-50' },
    { label: 'Reviewed',        value: s.reviewed ?? 0,
      colour: 'text-yellow-700', bg: 'bg-yellow-50' },
    { label: 'Blocked',         value: s.blocked ?? 0,
      colour: 'text-red-700', bg: 'bg-red-50' },
    { label: 'Fraud Rate',
      value: s.total_processed > 0
        ? `${((s.fraud_rate || 0) * 100).toFixed(2)}%`
        : '0.00%',
      colour: 'text-purple-700', bg: 'bg-purple-50' },
    { label: 'Avg Latency',
      value: `${s.avg_processing_ms ?? 0} ms`,
      colour: 'text-gray-700', bg: 'bg-gray-50' },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {cards.map(c => (
        <div key={c.label}
          className={`${c.bg} rounded-lg p-4 border border-gray-100`}>
          <p className="text-xs text-gray-500 mb-1">{c.label}</p>
          <p className={`text-2xl font-bold ${c.colour}`}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}