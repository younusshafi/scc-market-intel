import { useState } from 'react'

export default function BriefingCard({ briefing, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await fetch('http://localhost:8000/api/briefings/generate', { method: 'POST' })
      if (onRefresh) onRefresh()
    } catch (e) {
      console.error('Refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div
      className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6"
      style={{ borderTop: '3px solid transparent', borderImage: 'linear-gradient(to right, #3b82f6, #8b5cf6) 1', borderImageSlice: '1 1 0 0' }}
    >
      {/* Legend strip */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
            AI Executive Briefing
          </h3>
          <div className="flex items-center gap-2 text-[11px] font-semibold">
            <span className="text-red-400">ACT NOW</span>
            <span className="text-[#334155]">·</span>
            <span className="text-amber-400">WATCH</span>
            <span className="text-[#334155]">·</span>
            <span className="text-blue-400">POSITION</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {briefing && (
            <span className="text-xs text-[#5a6a85]">
              {timeAgo(briefing.generated_at)}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {refreshing ? '...' : 'Refresh'}
          </button>
        </div>
      </div>

      {briefing ? (
        <div
          className="text-sm text-[#c8d0de] leading-relaxed italic prose prose-invert prose-sm max-w-none prose-p:mb-3 prose-p:text-sm prose-strong:text-white"
          dangerouslySetInnerHTML={{ __html: briefing.content_html || formatMd(briefing.content_md) }}
        />
      ) : (
        <p className="text-sm text-[#5a6a85] italic">No briefing available yet.</p>
      )}
    </div>
  )
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now - d) / 1000)
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
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
