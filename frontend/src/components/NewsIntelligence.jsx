import { useState, useMemo } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const SOURCE_COLORS = {
  'Oman Observer': '#10b981',
  'Times of Oman': '#2563EB',
  'Google News': '#F59E0B',
}

function getSourceColor(source) {
  if (!source) return '#64748b'
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.toLowerCase().includes(key.toLowerCase())) return color
  }
  return '#64748b'
}

const CONFIDENCE_STYLES = {
  confirmed: 'bg-green-600 text-white',
  likely: 'bg-blue-600 text-white',
  possible: 'bg-slate-600 text-white',
  future_signal: 'bg-purple-600 text-white',
}

function LinkedTenders({ links }) {
  if (!links || links.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {links.map((link, i) => {
        const confStyle = CONFIDENCE_STYLES[link.match_confidence?.toLowerCase()] || CONFIDENCE_STYLES.possible
        return (
          <span key={i} className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${confStyle}`}>
            {link.tender_number || link.match_confidence?.replace('_', ' ')}
          </span>
        )
      })}
    </div>
  )
}

function ArticleCard({ article, tenderLinks }) {
  const priority = article.priority?.toLowerCase()
  const priorityStripe = priority === 'high' ? 'border-l-red-500' : priority === 'medium' ? 'border-l-amber-500' : 'border-l-slate-500'
  const sourceColor = getSourceColor(article.source)

  return (
    <div className={`bg-[#111827] border border-[#1e2a42] border-l-4 ${priorityStripe} rounded-lg p-5 hover:border-[#2a3a5c] transition-colors`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {article.source && (
            <span className="text-[10px] font-semibold text-white px-2 py-0.5 rounded" style={{ backgroundColor: sourceColor }}>
              {article.source}
            </span>
          )}
          <span className="text-xs text-[#5a6a85]">
            {article.published ? new Date(article.published).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
          priority === 'high' ? 'bg-red-500 text-white' : 'bg-amber-500 text-white'
        }`}>
          {article.priority?.toUpperCase()}
        </span>
      </div>

      {/* Headline */}
      <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-2">
        {article.title}
      </h4>

      {/* SCC Implication */}
      {article.scc_implication && (
        <div className="border-l-2 border-blue-500 bg-[#0a0e17] rounded-r-lg px-4 py-3">
          <p className="text-sm text-[#8896b0] leading-relaxed">
            <span className="text-blue-400 font-semibold mr-1">SCC Impact:</span>
            {article.scc_implication}
          </p>
        </div>
      )}

      {/* Linked tenders */}
      <LinkedTenders links={tenderLinks} />

      {/* Read link */}
      {article.link && (
        <a href={article.link} target="_blank" rel="noopener noreferrer"
          className="text-xs text-blue-400 hover:text-blue-300 mt-2 inline-block">
          Read article &rarr;
        </a>
      )}
    </div>
  )
}

export default function NewsIntelligence() {
  const { data, loading, error, refetch } = useAPI(api.getNewsIntelligence, [])
  const { data: linksData } = useAPI(api.getNewsTenderLinks, [])
  const [showLow, setShowLow] = useState(false)
  const [analysing, setAnalysing] = useState(false)

  const allArticles = (data?.articles || []).filter(a => a.relevant !== false)

  // Hide LOW priority by default
  const articles = showLow
    ? allArticles
    : allArticles.filter(a => a.priority?.toLowerCase() !== 'low')

  // Group tender links by article_id
  const linksByArticle = useMemo(() => {
    const map = {}
    for (const link of (linksData?.links || [])) {
      if (!map[link.article_id]) map[link.article_id] = []
      map[link.article_id].push(link)
    }
    return map
  }, [linksData])

  const priorityOrder = { high: 0, medium: 1, low: 2 }
  const sorted = [...articles].sort((a, b) =>
    (priorityOrder[a.priority?.toLowerCase()] ?? 3) - (priorityOrder[b.priority?.toLowerCase()] ?? 3)
  )

  const lowCount = allArticles.filter(a => a.priority?.toLowerCase() === 'low').length

  async function handleTriggerAnalysis() {
    setAnalysing(true)
    try {
      await api.triggerNewsAnalysis()
      await refetch()
    } catch (e) {
      console.error('News analysis failed:', e)
    } finally {
      setAnalysing(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
            News Intelligence
          </h2>
          {articles.length > 0 && (
            <span className="text-xs font-semibold bg-blue-600/20 text-blue-400 px-2.5 py-0.5 rounded-full">
              {articles.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {lowCount > 0 && (
            <button
              onClick={() => setShowLow(!showLow)}
              className="text-xs font-semibold text-[#5a6a85] hover:text-[#8896b0] transition-colors"
            >
              {showLow ? 'Hide' : 'Show'} {lowCount} low priority
            </button>
          )}
          <button
            onClick={handleTriggerAnalysis}
            disabled={analysing}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {analysing ? 'Analysing...' : 'Re-run'}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg h-28 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#111827] border border-red-900/50 rounded-lg p-6 text-center">
          <p className="text-sm text-red-400">Failed to load news intelligence</p>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && allArticles.length === 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-8 text-center">
          <p className="text-sm text-[#5a6a85]">No articles analysed yet</p>
          <button
            onClick={handleTriggerAnalysis}
            disabled={analysing}
            className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {analysing ? 'Running...' : 'Run AI Analysis'}
          </button>
        </div>
      )}

      {/* Article cards */}
      {!loading && !error && sorted.length > 0 && (
        <div className="space-y-3">
          {sorted.map((article, i) => (
            <ArticleCard key={article.id || i} article={article} tenderLinks={linksByArticle[article.id]} />
          ))}
        </div>
      )}
    </div>
  )
}
