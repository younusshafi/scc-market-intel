import { useState, useRef, useEffect } from 'react'
import { Send, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'
import { askNlq } from '../utils/api'

const EXAMPLE_QUESTIONS = [
  'Which tenders scored above 80 are closing in the next 21 days?',
  'What is SCC\'s win rate at Muscat Municipality?',
  'Who won the most awarded tenders in 2026?',
  'Show me recent news mentioning Galfar.',
  'Has Premier International bid on any MoT tender above OMR 20M in 2025?',
  'What\'s good for us this week?',
]

function TierBadge({ tier }) {
  if (tier === 1) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
        Instant
      </span>
    )
  }
  if (tier === 2) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-violet-500/15 text-violet-400 border border-violet-500/20">
        AI query
      </span>
    )
  }
  return null
}

function CaveatBlock({ caveats }) {
  if (!caveats || caveats.length === 0) return null
  return (
    <div className="mt-2.5 px-3 py-2 rounded-md bg-amber-500/5 border border-amber-500/15">
      <div className="flex items-start gap-2">
        <AlertTriangle size={13} className="text-amber-500/70 mt-0.5 flex-shrink-0" />
        <div className="space-y-1">
          {caveats.map((c, i) => (
            <p key={i} className="text-[11px] text-amber-200/70 leading-relaxed">{c}</p>
          ))}
        </div>
      </div>
    </div>
  )
}

function CollapsibleAudit({ sql, rows }) {
  const [open, setOpen] = useState(false)
  if (!sql && (!rows || rows.length === 0)) return null

  const columns = rows && rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[11px] text-[#5a6a85] hover:text-[#8896b0] transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Show query & data {rows && rows.length > 0 && `(${rows.length} row${rows.length !== 1 ? 's' : ''})`}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {sql && (
            <pre className="text-[11px] text-[#8896b0] bg-[#0a0e17] border border-[#1e2a42] rounded-md px-3 py-2 overflow-x-auto whitespace-pre-wrap break-words font-mono leading-relaxed">
              {sql}
            </pre>
          )}

          {rows && rows.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-[#1e2a42]">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="bg-[#0a0e17]">
                    {columns.map(col => (
                      <th key={col} className="px-2.5 py-1.5 text-left text-[#5a6a85] font-medium whitespace-nowrap border-b border-[#1e2a42]">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 50).map((row, ri) => (
                    <tr key={ri} className={ri % 2 === 0 ? 'bg-[#111827]' : 'bg-[#0f1520]'}>
                      {columns.map(col => (
                        <td key={col} className="px-2.5 py-1.5 text-[#8896b0] whitespace-nowrap border-b border-[#1e2a42]/50 max-w-[300px] truncate">
                          {row[col] != null ? String(row[col]) : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 50 && (
                <div className="px-2.5 py-1.5 text-[10px] text-[#5a6a85] bg-[#0a0e17] border-t border-[#1e2a42]">
                  Showing 50 of {rows.length} rows
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AssistantMessage({ msg }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg rounded-tl-sm px-4 py-3">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[11px] font-medium text-[#5a6a85]">Intel</span>
            <TierBadge tier={msg.tier} />
          </div>
          <div className="text-[13px] text-[#c8d2e0] leading-relaxed whitespace-pre-wrap">
            {msg.answer}
          </div>
          <CaveatBlock caveats={msg.caveats} />
          <CollapsibleAudit sql={msg.sql} rows={msg.rows} />
        </div>
      </div>
    </div>
  )
}

function UserMessage({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div className="bg-blue-600/20 border border-blue-500/20 rounded-lg rounded-tr-sm px-4 py-2.5">
          <p className="text-[13px] text-blue-100 leading-relaxed">{text}</p>
        </div>
      </div>
    </div>
  )
}

export default function AskIntel() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend(question) {
    const q = (question || input).trim()
    if (!q || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)

    try {
      const result = await askNlq(q)
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: result.answer || 'No response received.',
        sql: result.sql || '',
        rows: result.rows || [],
        tier: result.tier || 0,
        caveats: result.caveats || [],
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: 'Something went wrong. Please try again.',
        sql: '',
        rows: [],
        tier: 0,
        caveats: [],
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const showExamples = messages.length === 0

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 180px)', minHeight: '400px' }}>
      {/* Message area */}
      <div className="flex-1 overflow-y-auto space-y-3 pb-4 pr-1" style={{ scrollbarWidth: 'thin', scrollbarColor: '#1e2a42 transparent' }}>
        {showExamples && (
          <div className="flex flex-col items-center justify-center h-full space-y-6 py-8">
            <div className="text-center space-y-2">
              <h2 className="text-lg font-semibold text-[#e8ecf4]">Ask Intel</h2>
              <p className="text-sm text-[#5a6a85] max-w-md">
                Ask questions about tenders, awards, competitors and news in plain English.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-2xl px-4">
              {EXAMPLE_QUESTIONS.map((eq, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(eq)}
                  className="text-left text-[12px] text-[#8896b0] bg-[#111827] hover:bg-[#162440] border border-[#1e2a42] hover:border-blue-500/30 rounded-lg px-3 py-2 transition-all duration-150"
                >
                  {eq}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          msg.role === 'user'
            ? <UserMessage key={i} text={msg.text} />
            : <AssistantMessage key={i} msg={msg} />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#111827] border border-[#1e2a42] rounded-lg rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-[11px] text-[#5a6a85]">Querying intelligence...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-[#1e2a42] pt-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about tenders, awards, competitors..."
            disabled={loading}
            className="flex-1 bg-[#111827] border border-[#1e2a42] rounded-lg px-4 py-2.5 text-[13px] text-[#e8ecf4] placeholder-[#3d4f6a] focus:outline-none focus:border-blue-500/40 focus:ring-1 focus:ring-blue-500/20 disabled:opacity-50 transition-colors"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 bg-blue-600 hover:bg-blue-500 disabled:bg-[#1e2a42] disabled:text-[#3d4f6a] text-white rounded-lg px-4 py-2.5 transition-colors flex items-center gap-2"
          >
            <Send size={14} />
            <span className="hidden sm:inline text-[13px] font-medium">Send</span>
          </button>
        </div>
      </div>
    </div>
  )
}
