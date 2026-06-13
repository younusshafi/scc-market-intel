import { useState, useRef, useEffect, lazy, Suspense } from 'react'
import { api } from './utils/api'
import { useAPI } from './hooks/useAPI'
import TabNavigation from './components/TabNavigation'
import MetricCards from './components/MetricCards'
import TrendChart from './components/TrendChart'
import BriefingCard from './components/BriefingCard'
import CompetitiveBattlefield from './components/CompetitiveBattlefield'
import PriorityActions from './components/PriorityActions'
import GalfarProfile from './components/GalfarProfile'
import ScoredTenders from './components/ScoredTenders'
import NewsIntelligence from './components/NewsIntelligence'
import CompetitorProfiles from './components/CompetitorProfiles'
import EntityIntelligence from './components/EntityIntelligence'
import MarketContext from './components/MarketContext'
import ActiveBids from './components/ActiveBids'
import AskIntel from './components/AskIntel'

// Lazy-loaded — large component with heavy Recharts usage
const AwardedIntelligence = lazy(() => import('./components/AwardedIntelligence'))

const BRIEFING_CACHE_KEY = 'scc_last_briefing'

export default function App() {
  const { data: stats } = useAPI(api.getTenderStats, [])
  const { data: trend } = useAPI(api.getTenderTrend, [])
  const { data: compIntel } = useAPI(api.getCompetitiveIntel, [])
  const { data: scoredData } = useAPI(api.getScoredTenders, [])
  const { data: newsIntel } = useAPI(api.getNewsIntelligence, [])
  const { data: awardedStats } = useAPI(api.getAwardedStats, [])

  // Briefing — load from localStorage cache instantly, then refresh from API
  const [briefing, setBriefing] = useState(() => {
    try {
      const cached = localStorage.getItem(BRIEFING_CACHE_KEY)
      return cached ? JSON.parse(cached) : null
    } catch { return null }
  })
  const [briefingLoading, setBriefingLoading] = useState(true)
  const [briefingStale, setBriefingStale] = useState(true)

  useEffect(() => {
    api.getLatestBriefing()
      .then(fresh => {
        if (fresh?.briefing) {
          setBriefing(fresh.briefing)
          setBriefingStale(false)
          try { localStorage.setItem(BRIEFING_CACHE_KEY, JSON.stringify(fresh.briefing)) } catch {}
        }
      })
      .catch(() => {})
      .finally(() => setBriefingLoading(false))
  }, [])

  async function refetchBriefing() {
    setBriefingLoading(true)
    try {
      const fresh = await api.getLatestBriefing()
      if (fresh?.briefing) {
        setBriefing(fresh.briefing)
        setBriefingStale(false)
        try { localStorage.setItem(BRIEFING_CACHE_KEY, JSON.stringify(fresh.briefing)) } catch {}
      }
    } catch {}
    finally { setBriefingLoading(false) }
  }

  // Competitor profiles — lifted here to avoid duplicate fetches across tabs
  const [competitorProfiles, setCompetitorProfiles] = useState([])
  useEffect(() => {
    api.getCompetitorProfiles()
      .then(res => { if (res?.profiles) setCompetitorProfiles(res.profiles) })
      .catch(() => {})
  }, [])

  const [activeTab, setActiveTab] = useState('command-centre')
  const contentRef = useRef(null)

  function handleTabChange(tabId) {
    setActiveTab(tabId)
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Award Intelligence freshness — emerald dot if computed within last 24h
  const awardedDataFresh = (() => {
    const ts = awardedStats?.computed_at || awardedStats?.last_updated
    if (!ts) return false
    return Date.now() - new Date(ts).getTime() < 86_400_000
  })()

  // Notification dots
  const notifications = {}
  if (compIntel?.live_competitive?.length > 0) {
    notifications['competitive-intel'] = true
  }
  const highPriorityNews = (newsIntel?.articles || []).filter(a => a.priority?.toLowerCase() === 'high')
  if (highPriorityNews.length > 0) {
    notifications['market-news'] = true
  }
  if (awardedDataFresh) {
    notifications['award-intel'] = 'fresh'
  }

  // Tab summary bar
  const tabSummaries = {
    'competitive-intel': [
      `${compIntel?.live_competitive?.length || '—'} live competitive`,
      `${compIntel?.head_to_head?.length || '—'} head-to-head`,
      `${compIntel?.activity_summary?.length || '—'} tracked competitors`,
    ].join(' · '),
    'opportunities': [
      `${scoredData?.total || '—'} scored`,
      `${(scoredData?.tenders || []).filter(t => t.score >= 70).length || '—'} matched SCC profile`,
    ].join(' · '),
    'market-news': [
      `${newsIntel?.total || '—'} articles`,
      `${highPriorityNews.length || '—'} high priority`,
    ].join(' · '),
    'award-intel': [
      '28,529 awarded contracts',
      'SCC win rate · competitor trends · pricing intelligence',
    ].join(' · '),
    'profiles': [
      `${competitorProfiles.length || '—'} competitor profiles`,
    ].join(' · '),
  }

  return (
    <div className="min-h-screen bg-[#0F172A]">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-[#020617] border-b border-[#1e2a42] px-4 sm:px-8 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7 flex-shrink-0">
            <rect width="28" height="28" rx="6" fill="#3B82F6" />
            <path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="text-lg font-bold text-[#e8ecf4] tracking-tight">Market Intelligence</span>
            <span className="hidden sm:inline text-xs text-[#5a6a85] ml-2">Sarooj Construction Company</span>
          </div>
        </div>
        <div className="flex items-center gap-3 sm:gap-4">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-red-500 uppercase tracking-wider">
            <span className="w-[6px] h-[6px] rounded-full bg-red-500 animate-pulse" />
            LIVE
          </span>
          <span className="hidden sm:inline text-[10px] text-[#5a6a85]">
            Powered by <strong className="text-[#8896b0]">Zavia-ai</strong>
          </span>
          <div className="w-7 h-7 rounded-full bg-[#1e2a42] border border-[#334155] flex items-center justify-center text-[10px] font-semibold text-[#8896b0]">
            JF
          </div>
        </div>
      </nav>

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} notifications={notifications} />

      {/* Tab Summary Bar */}
      {activeTab !== 'command-centre' && tabSummaries[activeTab] && (
        <div className="bg-[#0a0e17] border-b border-[#1e2a42] px-4 sm:px-8 py-1.5">
          <div className="max-w-[1400px] mx-auto">
            <p className="text-xs text-[#5a6a85] font-mono">{tabSummaries[activeTab]}</p>
          </div>
        </div>
      )}

      {/* Content */}
      <main ref={contentRef} className="max-w-[1400px] mx-auto px-4 sm:px-8 py-5 space-y-5">

        {/* TAB 1: Command Centre */}
        {activeTab === 'command-centre' && (
          <>
            <ActiveBids />
            <PriorityActions />
            <MetricCards />
            <BriefingCard
              briefing={briefing}
              loading={briefingLoading}
              isStale={briefingStale}
              onRefresh={refetchBriefing}
            />
            <TrendChart data={trend} />
          </>
        )}

        {/* TAB 2: Competitive Intel */}
        {activeTab === 'competitive-intel' && (
          <>
            <CompetitiveBattlefield />
            <CompetitorProfiles profiles={competitorProfiles} />
          </>
        )}

        {/* TAB 3: Opportunities */}
        {activeTab === 'opportunities' && (
          <ScoredTenders />
        )}

        {/* TAB 4: Award Intelligence */}
        {activeTab === 'award-intel' && (
          <Suspense fallback={
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg h-40 animate-pulse" />
              ))}
            </div>
          }>
            <AwardedIntelligence />
          </Suspense>
        )}

        {/* TAB 5: Market & News */}
        {activeTab === 'market-news' && (
          <>
            <NewsIntelligence />
            <EntityIntelligence />
            <MarketContext stats={stats} />
          </>
        )}

        {/* TAB 6: Profiles */}
        {activeTab === 'profiles' && (
          <>
            <GalfarProfile />
            <CompetitorProfiles profiles={competitorProfiles} />
          </>
        )}

        {/* TAB 7: Ask Intel */}
        {activeTab === 'ask-intel' && (
          <AskIntel />
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-[#1e2a42] px-8 py-5 text-center text-[10px] text-[#5a6a85] mt-6">
        Data sourced from etendering.tenderboard.gov.om &middot; Oman news RSS &middot; Google News
        <br />
        Powered by <strong className="text-[#8896b0]">Zavia-ai</strong> &middot; Intelligence refresh: daily
      </footer>
    </div>
  )
}
