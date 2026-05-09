import { useState } from 'react'
import { api } from '../utils/api'

// Section config — matches the 5 AI briefing sections
const SECTION_CONFIG = {
  'BID NOW':          { color: 'border-red-500',    badge: 'bg-red-500/15 text-red-400 border-red-500/40',    dot: 'bg-red-500'    },
  'WATCH':            { color: 'border-amber-500',  badge: 'bg-amber-500/15 text-amber-400 border-amber-500/40',  dot: 'bg-amber-500'  },
  'COMPETITOR ALERT': { color: 'border-orange-500', badge: 'bg-orange-500/15 text-orange-400 border-orange-500/40', dot: 'bg-orange-500' },
  'MARKET PULSE':     { color: 'border-blue-500',   badge: 'bg-blue-500/15 text-blue-400 border-blue-500/40',   dot: 'bg-blue-500'   },
  'STRATEGIC NOTE':   { color: 'border-purple-500', badge: 'bg-purple-500/15 text-purple-400 border-purple-500/40', dot: 'bg-purple-500' },
}

/** Parse "**SECTION TITLE**\n body text" blocks out of markdown/html content */
function parseSections(content) {
  if (!content) return []
  // Strip HTML tags for section parsing
  const text = content.replace(/<[^>]+>/g, '').replace(/&middot;/g, '·')

  const sectionKeys = Object.keys(SECTION_CONFIG)
  const found = []

  for (const key of sectionKeys) {
    // Match ** KEY ** or plain KEY at line start
    const patterns = [
      new RegExp(`\\*\\*${key}\\*\\*[:\\s]*([\\s\\S]*?)(?=\\*\\*(?:${sectionKeys.join('|')})\\*\\*|$)`, 'i'),
      new RegExp(`^${key}[:\\s]+([\\s\\S]*?)(?=^(?:${sectionKeys.join('|')})[:\\s]|$)`, 'im'),
    ]
    for (const re of patterns) {
      const m = text.match(re)
      if (m && m[1]?.trim()) {
        found.push({ key, body: m[1].trim() })
        break
      }
    }
  }

  // If no sections parsed, return raw content as a single prose block
  if (found.length === 0) return null
  return found
}

function formatTimestamp(dateStr) {
  if (!dateStr) return null
  return new Date(dateStr).toLocaleString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })
}

function hoursAgo(dateStr) {
  if (!dateStr) return null
  return Math.round((Date.now() - new Date(dateStr).getTime()) / 3_600_000)
}

function formatMd(md) {
  if (!md) return ''
  return md
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

export default function BriefingCard({ briefing, loading, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)
  const [rawView, setRawView] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.generateBriefing()
      if (onRefresh) onRefresh()
    } catch (e) {
      console.error('Briefing refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }

  const age = briefing ? hoursAgo(briefing.generated_at) : null
  const isStale = age !== null && age > 24

  const htmlContent = briefing?.content_html || formatMd(briefing?.content_md)
  const sections = briefing ? parseSections(briefing.content_md || briefing.content_html) : null

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-xl overflow-hidden"
      style={{ borderTop: '2px solid', borderImageSource: 'linear-gradient(to right, #3b82f6, #8b5cf6)', borderImageSlice: 1 }}>

      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
            AI Executive Briefing
          </h3>
          {briefing && (
            <div className="flex items-center gap-1.5 text-[10px]">
              {Object.keys(SECTION_CONFIG).map(k => (
                <span key={k} className={`font-bold border px-1.5 py-0.5 rounded text-[9px] ${SECTION_CONFIG[k].badge}`}>
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          {briefing && (
            <span className={`text-[10px] font-mono ${isStale ? 'text-amber-400' : 'text-[#5a6a85]'}`}>
              {isStale ? `⚠ ${age}h ago` : formatTimestamp(briefing.generated_at)}
            </span>
          )}
          {sections && (
            <button
              onClick={() => setRawView(!rawView)}
              className="text-[10px] text-[#5a6a85] hover:text-[#8896b0] transition-colors"
            >
              {rawView ? 'Sections' : 'Full text'}
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors flex items-center gap-1.5"
          >
            <svg className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing ? 'Generating…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && !briefing && (
        <div className="px-6 pb-6 space-y-2 animate-pulse">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-3 bg-[#1e2a42] rounded" style={{ width: `${75 + i * 4}%` }} />
          ))}
        </div>
      )}

      {/* No briefing yet */}
      {!loading && !briefing && (
        <div className="px-6 pb-6">
          <p className="text-sm text-[#5a6a85] italic">No briefing generated yet.</p>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {refreshing ? 'Generating…' : 'Generate Briefing'}
          </button>
        </div>
      )}

      {/* Sections view */}
      {briefing && sections && !rawView && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-0 border-t border-[#1e2a42]">
          {sections.map(({ key, body }) => {
            const cfg = SECTION_CONFIG[key]
            return (
              <div key={key} className={`border-l-2 ${cfg.color} px-5 py-4 border-r border-[#1e2a42] last:border-r-0`}>
                <div className={`text-[9px] font-bold tracking-widest mb-2 uppercase ${cfg.badge.split(' ')[1]}`}>
                  {key}
                </div>
                <p className="text-xs text-[#c8d0de] leading-relaxed">{body}</p>
              </div>
            )
          })}
        </div>
      )}

      {/* Raw / fallback prose view */}
      {briefing && (!sections || rawView) && (
        <div
          className="px-6 pb-6 text-sm text-[#c8d0de] leading-relaxed italic prose prose-invert prose-sm max-w-none prose-p:mb-3 prose-p:text-sm prose-strong:text-white border-t border-[#1e2a42] pt-4"
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      )}
    </div>
  )
}
