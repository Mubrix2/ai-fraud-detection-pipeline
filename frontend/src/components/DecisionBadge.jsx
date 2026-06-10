// frontend/src/components/DecisionBadge.jsx
const STYLES = {
  BLOCK:   'bg-red-100 text-red-800 border border-red-300',
  REVIEW:  'bg-yellow-100 text-yellow-800 border border-yellow-300',
  APPROVE: 'bg-green-100 text-green-800 border border-green-300',
}
const ICONS = { BLOCK: '🚫', REVIEW: '🔍', APPROVE: '✅' }

export default function DecisionBadge({ decision }) {
  const d = decision || 'UNKNOWN'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold
      ${STYLES[d] || 'bg-gray-100 text-gray-500'}`}>
      {ICONS[d] || '—'} {d}
    </span>
  )
}