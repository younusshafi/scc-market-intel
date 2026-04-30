import { useState, useEffect } from 'react'
import { api } from '../utils/api'

const SOURCE_COLORS = {
  'Oman Observer': '#10b981',
  'Times of Oman': '#3b82f6',
  'Google News': '#f59e0b',
}

function getSourceColor(source) {
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.toLowerCase().includes(key.toLowerCase())) return color
  }
  return '#64748b'
}

function ArticleCard({ article }) {
  const color = getSourceColor(article.source)
  const shortSource = article.source
    .replace('Oman Observer \u2014 ', '')
    .replace('Google News \u2014 ', '')
    .replace('Times of Oman \u2014 ', '')

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-4 hover:bg-[#253347] transition-all">
      <div className="flex justify-between items-center mb-2">
        <span
          className="text-[9px] font-semibold text-white px-2 py-0.5 rounded-full uppercase tracking-wider"
          style={{ backgroundColor: color }}
        >
          {shortSource}
        </span>
        <span className="text-[10px] text-[#5a6a85]">
          {article.published ? new Date(article.published).toLocaleDateString() : ''}
        </span>
      </div>
      <h4 className="text-[13px] font-semibold text-white mb-1 leading-snug">{article.title}</h4>
      <p className="text-xs text-[#8896b0] mb-2 line-clamp-3">{article.summary}</p>
      {article.link && (
        <a
          href={article.link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-semibold text-blue-400 hover:text-blue-300"
        >
          Read article \u2192
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

  const competitorNews = articles.filter(a => a.is_competitor_mention)
  const marketNews = articles.filter(a => !a.is_competitor_mention)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Competitor News */}
      <div>
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          Competitor News
          <span className="text-[10px] text-[#8896b0] normal-case tracking-normal font-normal">({competitorNews.length})</span>
        </h3>
        <div className="space-y-3">
          {competitorNews.length > 0 ? (
            competitorNews.map((a) => <ArticleCard key={a.id} article={a} />)
          ) : (
            <p className="text-sm text-[#5a6a85] italic">No competitor mentions found.</p>
          )}
        </div>
      </div>

      {/* Market & Policy News */}
      <div>
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          Market &amp; Policy News
          <span className="text-[10px] text-[#8896b0] normal-case tracking-normal font-normal">({marketNews.length})</span>
        </h3>
        <div className="space-y-3">
          {marketNews.length > 0 ? (
            marketNews.map((a) => <ArticleCard key={a.id} article={a} />)
          ) : (
            <p className="text-sm text-[#5a6a85] italic">No market news found.</p>
          )}
        </div>
      </div>
    </div>
  )
}
