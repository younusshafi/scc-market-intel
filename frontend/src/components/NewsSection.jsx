import { useState, useEffect } from 'react'
import { api } from '../utils/api'

const SOURCE_COLORS = {
  'Times of Oman': '#3B82F6',
  'Oman Observer': '#10B981',
  'Construction': '#F59E0B',
  'Infrastructure': '#7C3AED',
}

function getSourceColor(source) {
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.toLowerCase().includes(key.toLowerCase())) return color
  }
  if (['galfar', 'strabag', 'tasnim', 'l&t', 'towell', 'hassan', 'arab', 'ozkar']
    .some(c => source.toLowerCase().includes(c))) return '#EF4444'
  return '#64748B'
}

export default function NewsSection() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [competitorOnly, setCompetitorOnly] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.getNews({ competitor_only: competitorOnly || undefined, page_size: 50 })
      .then((res) => setArticles(res.articles))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [competitorOnly])

  if (loading) {
    return <div className="text-center text-slate-500 py-8">Loading news...</div>
  }

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setCompetitorOnly(false)}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors
            ${!competitorOnly ? 'bg-blue-500 text-white' : 'border border-slate-700 text-slate-400'}`}
        >All News</button>
        <button
          onClick={() => setCompetitorOnly(true)}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors
            ${competitorOnly ? 'bg-red-500 text-white' : 'border border-slate-700 text-slate-400'}`}
        >Competitor Only</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {articles.map((a) => {
          const color = getSourceColor(a.source)
          const shortSource = a.source
            .replace('Oman Observer — ', '')
            .replace('Google News — ', '')
          const isComp = a.is_competitor_mention
          const label = isComp ? `COMPETITOR · ${shortSource}` : shortSource

          return (
            <div
              key={a.id}
              className="bg-surface border border-slate-700/50 rounded-xl p-4 flex flex-col hover:bg-surface-hover transition-all hover:-translate-y-0.5"
            >
              <div className="flex justify-between items-center mb-1.5">
                <span
                  className="text-[9px] font-semibold text-white px-2 py-0.5 rounded-full uppercase tracking-wider"
                  style={{ backgroundColor: color }}
                >
                  {label}
                </span>
                <span className="text-[10px] text-slate-500">
                  {a.published ? new Date(a.published).toLocaleDateString() : ''}
                </span>
              </div>
              <h4 className="text-[13px] font-semibold text-white mb-1 leading-snug">{a.title}</h4>
              <p className="text-xs text-slate-500 flex-1 mb-2 line-clamp-3">{a.summary}</p>
              <a
                href={a.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] font-semibold text-blue-400 hover:text-blue-300"
              >
                Read →
              </a>
            </div>
          )
        })}
      </div>

      {articles.length === 0 && (
        <p className="text-center text-slate-500 py-8">No news articles found.</p>
      )}
    </div>
  )
}
