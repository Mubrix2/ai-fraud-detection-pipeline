// frontend/src/components/TransactionTable.jsx
import DecisionBadge from './DecisionBadge'

export default function TransactionTable({ transactions, selected, onSelect }) {
  if (!transactions.length) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg font-medium">No transactions yet</p>
        <p className="text-sm mt-1">Submit a transaction above to begin</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-100">
            {['Transaction ID','Type','Amount (₦)','Decision',
              'Fraud Prob','Anomaly','AML','ms'].map(h => (
              <th key={h}
                className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transactions.map(tx => {
            const isSelected = selected?.transaction_id === tx.transaction_id
            const rowBg =
              tx.decision === 'BLOCK'  ? 'bg-red-50 hover:bg-red-100' :
              tx.decision === 'REVIEW' ? 'bg-yellow-50 hover:bg-yellow-100' :
              'bg-white hover:bg-gray-50'
            const isAuto = tx.note?.includes('Auto-approved')

            return (
              <tr
                key={tx.transaction_id}
                onClick={() => onSelect(tx)}
                className={`
                  border-b border-gray-100 cursor-pointer transition-colors
                  ${rowBg}
                  ${isSelected ? 'ring-2 ring-inset ring-blue-400' : ''}
                `}
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  {tx.transaction_id?.slice(0, 18)}…
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {tx.transaction?.type ?? '—'}
                </td>
                <td className="px-4 py-3 font-medium text-right">
                  {Number(tx.transaction?.amount ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <DecisionBadge decision={tx.decision} />
                </td>
                <td className="px-4 py-3 text-right">
                  {isAuto ? (
                    <span className="text-xs text-gray-400 italic">—</span>
                  ) : (
                    <span className={
                      tx.fraud_probability > 0.85 ? 'text-red-600 font-semibold' :
                      tx.fraud_probability > 0.60 ? 'text-yellow-600 font-medium' :
                      'text-gray-600'
                    }>
                      {(tx.fraud_probability * 100).toFixed(1)}%
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {tx.anomaly_label ?? '—'}
                </td>
                <td className="px-4 py-3 text-center">
                  {tx.aml_flag_count > 0 ? (
                    <span className="text-xs text-orange-600 font-semibold">
                      ⚠ {tx.aml_flag_count}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-300">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-xs text-gray-400">
                  {tx.processing_ms?.toFixed(0) ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}