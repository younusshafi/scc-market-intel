import { useState, useMemo } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const PRIORITY_STYLES = {
  high: 'bg-red-600 text-white',
  medium: 'bg-amber-600 text-white',
  low: 'bg-slate-600 text-white',
}

const CATEGORY_STYLES = {
  competitor: 'border-red-500 text-red-400',
  infrastructure: 'border-blue-500 text-blue-400',
  tender_signal: 'border-green-500 text-green-400',
  policy: 'border-purple-500 text-purple-400',
  market: 'border-cyan-500 text-cyan-400',
}

const SOURCE_COLORS = {
  'Oman Observer': '#10b981',
  'Times of Oman': '#2563EB',
  'Google News Oman Construction': '#F59E0B',
  'Google News Oman Infrastructure': '#7C3AED',
}

function getSourceColor(source) {
  if (!source) return '#64748b'
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.toLowerCase().includes(key.toLowerCase())) return color
  }
  return '#64748b'
}

function formatCategory(cat) {
  if (!cat) return cat
  return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const CONFIDENCE_STYLES = {
  confirmed: 'bg-green-600 text-white',
  likely: 'bg-blue-600 text-white',
  possible: 'bg-slate-600 text-white',
  future_signal: 'bg-purple-600 text-white',
}

function LinkedTenders({ links }) {
  const [expanded, setExpanded] = useState(false)

  if (!links || links.length === 0) return null

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[10px] font-semibold text-green-400 hover:text-green-300 transition-colors flex items-center gap-1"
      >
        <span>{expanded ? '\u25BC' : '\u25B6'}</span>
        Linked Tenders ({links.length})
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {links.map((link, i) => {
            const confStyle = CONFIDENCE_STYLES[link.match_confidence?.toLowerCase()] || CONFIDENCE_STYLES.possible
            const isFutureSignal = link.match_confidence === 'future_signal'

            return (
              <div key={i} className="bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full uppercase ${confStyle}`}>
                    {link.match_confidence?.replace('_', ' ') || 'possible'}
                  </span>
                  {link.tender_number && (
                    <span className="text-[10px] font-mono text-[#8896b0]">{link.tender_number}</span>
                  )}
                </div>
                <p className="text-[11px] text-[#8896b0] leading-relaxed">
                  {isFutureSignal
                    ? 'No active tender yet \u2014 monitor entity for upcoming publication.'
                    : link.connection
                  }
                </p>
                {link.scc_action && !isFutureSignal && (
                  <p className="text-[10px] text-green-400 mt-1">
                    {link.scc_action}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function ArticleCard({ article, tenderLinks }) {
  const priorityStyle = PRIORITY_STYLES[article.priority?.toLowerCase()] || PRIORITY_STYLES.low
  const catStyle = CATEGORY_STYLES[article.intel_category?.toLowerCase()] || 'border-slate-500 text-slate-400'
  const sourceColor = getSourceColor(article.source)

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 hover:bg-[#253347] transition-colors">
      {/* Top row: priority + category + source + date */}
      <div className="flex flex-wrap items-center gap-2 mb-2.5">
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${priorityStyle}`}>
          {article.priority?.toUpperCase() || 'LOW'}
        </span>
        {article.intel_category && (
          <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border ${catStyle}`}>
            {formatCategory(article.intel_category)}
          </span>
        )}
        {article.source && (
          <span
            className="text-[9px] font-semibold text-white px-2 py-0.5 rounded-full"
            style={{ backgroundColor: sourceColor }}
          >
            {article.source}
          </span>
        )}
        <span className="text-[10px] text-[#5a6a85] ml-auto">
          {article.published ? new Date(article.published).toLocaleDateString() : ''}
        </span>
      </div>

      {/* Headline */}
      <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-2">
        {article.title}
      </h4>

      {/* Summary */}
      {article.summary && (
        <p className="text-xs text-[#8896b0] mb-3 leading-relaxed line-clamp-2">
          {article.summary}
        </p>
      )}

      {/* SCC Implication */}
      {article.scc_implication && (
        <div className="border-l-2 border-blue-500 bg-[#0F172A] rounded-r-lg px-3 py-2.5 mb-3">
          <p className="text-[11px] text-[#8896b0] italic leading-relaxed">
            <span className="text-blue-400 font-semibold not-italic mr-1">SCC Impact:</span>
            {article.scc_implication}
          </p>
        </div>
      )}

      {/* Linked Tenders */}
      <LinkedTenders links={tenderLinks} />

      {/* Link */}
      {article.link && (
        <a
          href={article.link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] text-blue-400 hover:text-blue-300 font-medium transition-colors mt-2 inline-block"
        >
          Read article &rarr;
        </a>
      )}
    </div>
  )
}

export default function NewsIntelligence() {
  const { data, loading, error, refetch } = useAPI(api.getNewsIntelligence, [])
  const { data: linksData } = useAPI(api.getNewsTenderLinks, [])
  const [analysing, setAnalysing] = useState(false)
  const [linking, setLinking] = useState(false)

  const articles = (data?.articles || []).filter(a => a.relevant !== false)

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
  const total = data?.total || articles.length

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

  async function handleLinkTenders() {
    setLinking(true)
    try {
      await api.linkNewsToTenders()
      await refetch()
    } catch (e) {
      console.error('News-tender linking failed:', e)
    } finally {
      setLinking(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">
            AI News Intelligence
          </h2>
          {total > 0 && (
            <span className="text-[10px] font-semibold bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded-full">
              {total}
            </span>
          )}
        </div>
        {articles.length > 0 && (
          <div className="flex items-center gap-3">
            <button
              onClick={handleLinkTenders}
              disabled={linking}
              className="text-[10px] font-semibold text-green-400 hover:text-green-300 disabled:opacity-50 transition-colors"
            >
              {linking ? 'Linking...' : 'Link to Tenders'}
            </button>
            <button
              onClick={handleTriggerAnalysis}
              disabled={analysing}
              className="text-[10px] font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
            >
              {analysing ? 'Analysing...' : 'Re-run Analysis'}
            </button>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 animate-pulse">
              <div className="flex gap-2 mb-3">
                <div className="h-4 w-12 bg-[#334155] rounded-full" />
                <div className="h-4 w-20 bg-[#334155] rounded-full" />
              </div>
              <div className="h-4 bg-[#334155] rounded w-3/4 mb-2" />
              <div className="h-3 bg-[#334155] rounded w-full mb-2" />
              <div className="h-12 bg-[#0F172A] rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#1E293B] border border-red-900/50 rounded-xl p-6 text-center">
          <p className="text-sm text-red-400 mb-2">Failed to load news intelligence</p>
          <p className="text-xs text-[#5a6a85]">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && articles.length === 0 && (
        <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-8 text-center">
          <p className="text-sm text-[#8896b0] mb-3">No articles analysed yet</p>
          <button
            onClick={handleTriggerAnalysis}
            disabled={analysing}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {analysing ? 'Running AI Analysis...' : 'Run AI Analysis'}
          </button>
        </div>
      )}

      {/* Article cards */}
      {!loading && !error && articles.length > 0 && (
        <div className="space-y-3">
          {sorted.map((article, i) => (
            <ArticleCard key={article.id || i} article={article} tenderLinks={linksByArticle[article.id]} />
          ))}
        </div>
      )}
    </div>
  )
}
