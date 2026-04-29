import { useState } from 'react'
import { Sparkles, X, Loader2 } from 'lucide-react'
import { api } from '../utils/api'

const SUGGESTIONS = [
  'How many SCC tenders?',
  'Tenders closing this week',
  'Show re-tenders',
  'News about Galfar',
  'Pipeline summary',
  'Market breakdown',
  'Top entities',
  'Competitor news',
]

export default function QueryBar() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (q) => {
    const text = q || query
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.query(text.trim())
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSubmit()
  }

  const clear = () => {
    setResult(null)
    setError(null)
    setQuery('')
  }

  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-5">
      {/* Input row */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400" />
          <input
            type="text"
            placeholder="Ask about tenders, news, or market data..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-10 pr-10 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30"
          />
          {(query || result) && (
            <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <button
          onClick={() => handleSubmit()}
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Ask'}
        </button>
      </div>

      {/* Suggestion chips */}
      {!result && !loading && (
        <div className="flex flex-wrap gap-2 mt-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => { setQuery(s); handleSubmit(s) }}
              className="px-3 py-1 bg-slate-800 border border-slate-700/50 rounded-full text-xs text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {result && <QueryResult result={result} />}
    </div>
  )
}

function QueryResult({ result }) {
  return (
    <div className="mt-4 space-y-3">
      {/* Message */}
      <p className="text-sm text-slate-200 font-medium">{result.message}</p>

      {/* Stat or summary */}
      {(result.type === 'stat' || result.type === 'summary') && result.data && (
        <div className="flex flex-wrap gap-3">
          {Object.entries(result.data).map(([key, val]) => {
            if (typeof val === 'object') return null
            return (
              <div key={key} className="bg-slate-800 rounded-lg px-4 py-2">
                <div className="text-xs text-slate-500 capitalize">{key.replace(/_/g, ' ')}</div>
                <div className="text-lg font-bold text-white">{typeof val === 'number' && key.includes('pct') ? `${val}%` : val}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Breakdown */}
      {result.type === 'breakdown' && result.data && (
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {result.data.map((item, i) => {
            const label = item.category || item.entity
            const pct = item.pct
            return (
              <div key={i} className="flex items-center gap-3">
                <span className="text-xs text-slate-400 w-48 truncate" title={label}>{label}</span>
                <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                  {pct != null && <div className="bg-blue-500 h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />}
                </div>
                <span className="text-xs text-slate-300 w-12 text-right">{item.count}</span>
                {pct != null && <span className="text-xs text-slate-500 w-12 text-right">{pct}%</span>}
              </div>
            )
          })}
        </div>
      )}

      {/* List (tenders or articles) */}
      {result.type === 'list' && result.data && (
        <div className="overflow-x-auto rounded-lg border border-slate-700/50 max-h-80 overflow-y-auto">
          <table className="w-full text-sm">
            <tbody>
              {result.data.map((item, i) => (
                <tr key={i} className="border-b border-slate-700/30 hover:bg-blue-500/5">
                  {item.tender_number ? (
                    <>
                      <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{item.tender_number}</td>
                      <td className="px-3 py-2 text-slate-200 max-w-[300px] truncate">{item.name}</td>
                      <td className="px-3 py-2 text-slate-400">{item.entity}</td>
                      <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{item.bid_closing || '—'}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2 text-slate-200 max-w-[400px]">
                        {item.link ? (
                          <a href={item.link} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 transition-colors">
                            {item.title}
                          </a>
                        ) : item.title}
                      </td>
                      <td className="px-3 py-2 text-slate-400">{item.source}</td>
                      <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{item.published?.split('T')[0] || '—'}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
