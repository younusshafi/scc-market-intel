import { useState, useEffect } from 'react'
import { api } from '../utils/api'

const SOURCE_COLORS = {
  'Oman Observer': '#10b981',
  'Times of Oman': '#2563EB',
  'Google News Oman Construction': '#F59E0B',
  'Google News Oman Infrastructure': '#7C3AED',
  'COMPETITOR': '#EF4444',
}

function getSourceColor(source, isCompetitor) {
  if (isCompetitor) return SOURCE_COLORS['COMPETITOR']
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.toLowerCase().includes(key.toLowerCase())) return color
  }
  return '#64748b'
}

function ArticleCard({ article }) {
  const isCompetitor = article.is_competitor_mention
  const color = getSourceColor(article.source, isCompetitor)

  const sourceLabel = isCompetitor
    ? `COMPETITOR \u00B7 ${article.competitor_name || 'Unknown'}`
    : article.source

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-4 hover:bg-[#253347] transition-all flex flex-col">
      <div className="flex justify-between items-center mb-2">
        <span
          className="text-[9px] font-semibold text-white px-2 py-0.5 rounded-full uppercase tracking-wider"
          style={{ backgroundColor: color }}
        >
          {sourceLabel}
        </span>
        <span className="text-[10px] text-[#5a6a85]">
          {article.published ? new Date(article.published).toLocaleDateString() : ''}
        </span>
      </div>
      <h4 className="text-[13px] font-bold text-white mb-1 leading-snug">{article.title}</h4>
      <p className="text-xs text-[#5a6a85] mb-3 line-clamp-3 flex-1">{article.summary}</p>
      {article.link && (
        <a
          href={article.link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-semibold text-blue-400 hover:text-blue-300"
        >
          Read &rarr;
        </a>
      )}
    </div>
  )
}

export default function NewsSection() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getNews({ page_size: 50 })
      .then((res) => setArticles(res.articles || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
        <p className="text-center text-[#5a6a85] py-8">Loading news...</p>
      </div>
    )
  }

  if (articles.length === 0) {
    return (
      <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
        <p className="text-center text-[#5a6a85] py-8 italic">No news articles found.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {articles.map((a) => (
        <ArticleCard key={a.id} article={a} />
      ))}
    </div>
  )
}
