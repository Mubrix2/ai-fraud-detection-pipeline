// frontend/src/components/InvestigationPanel.jsx
import { useState } from 'react'
import { investigate } from '../api/client'

const EXAMPLE_QUESTIONS = [
  'Why was the last transaction flagged?',
  'List the last 5 blocked transactions',
  'Generate an investigation report for the most recent BLOCK',
]

export default function InvestigationPanel() {
  const [question, setQuestion]   = useState('')
  const [answer,   setAnswer]     = useState(null)
  const [loading,  setLoading]    = useState(false)
  const [error,    setError]      = useState(null)

  const ask = async (q) => {
    const text = q || question
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setAnswer(null)
    try {
      const resp = await investigate(text)
      setAnswer(resp.answer)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mt-6">
      <h2 className="font-semibold text-gray-800 mb-1">
        AI Investigation Agent
      </h2>
      <p className="text-xs text-gray-400 mb-3">
        Ask questions about flagged transactions in natural language.
      </p>

      {/* Example questions */}
      <div className="flex flex-wrap gap-2 mb-3">
        {EXAMPLE_QUESTIONS.map(q => (
          <button key={q}
            onClick={() => { setQuestion(q); ask(q) }}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-600
              rounded hover:bg-gray-200 border border-gray-200">
            {q}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex gap-2 mb-3">
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ask()}
          placeholder="Ask about any transaction..."
          className="flex-1 text-sm border border-gray-200 rounded
            px-3 py-2 focus:outline-none focus:border-blue-400"
        />
        <button
          onClick={() => ask()}
          disabled={loading || !question.trim()}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium
            rounded hover:bg-blue-700 disabled:opacity-50">
          {loading ? '...' : 'Ask'}
        </button>
      </div>

      {/* Answer */}
      {answer && (
        <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700
          whitespace-pre-wrap border border-gray-200 font-mono leading-relaxed">
          {answer}
        </div>
      )}
      {error && (
        <div className="text-xs text-red-600 mt-2">Error: {error}</div>
      )}
    </div>
  )
}