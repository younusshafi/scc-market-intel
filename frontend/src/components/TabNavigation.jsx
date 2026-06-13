import { useRef, useState } from 'react'
import { LayoutDashboard, Swords, Target, Newspaper, UserSearch, BarChart2, MessageCircle } from 'lucide-react'

const TABS = [
  { id: 'command-centre',    label: 'Command Centre',    icon: LayoutDashboard },
  { id: 'competitive-intel', label: 'Competitive Intel', icon: Swords },
  { id: 'opportunities',     label: 'Opportunities',     icon: Target },
  { id: 'award-intel',       label: 'Award Intelligence',icon: BarChart2 },
  { id: 'market-news',       label: 'Market & News',     icon: Newspaper },
  { id: 'profiles',          label: 'Profiles',          icon: UserSearch },
  { id: 'ask-intel',          label: 'Ask Intel',         icon: MessageCircle },
]

// Task 3 — tooltip descriptions for each tab
const TOOLTIPS = {
  'command-centre':    'KPIs, AI briefing, priority actions and tender volume trend',
  'competitive-intel': 'Live competitor tracking, head-to-head bids and activity summary',
  'opportunities':     'AI-scored tenders filtered for SCC grade and category',
  'award-intel':       'Historical wins, competitor participation and head-to-head data',
  'market-news':       'Live news feed, entity intelligence and ministry profiles',
  'profiles':          'Galfar financials, competitor summaries and watchlist',
  'ask-intel':         'Ask questions in plain English about tenders, awards, competitors and news',
}

export default function TabNavigation({ activeTab, onTabChange, notifications = {} }) {
  const tabRef = useRef(null)
  const [scrolledToEnd, setScrolledToEnd] = useState(false)

  function handleScroll(e) {
    const el = e.target
    setScrolledToEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4)
  }

  return (
    // Task 1 — pill-style segmented nav container
    <div className="sticky top-[57px] z-40 bg-[#080d18] border-b border-[#1e2a42]">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-2.5">
        <div className="relative">
          {/* Pill container — glass background */}
          <div
            ref={tabRef}
            className="flex flex-wrap gap-1 p-1 bg-[#0a0e1a] border border-[#1e2a42] rounded-xl w-fit max-w-full overflow-x-auto"
            style={{ scrollbarWidth: 'none' }}
            onScroll={handleScroll}
          >
            {TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              const notif = notifications[tab.id]
              const tooltip = TOOLTIPS[tab.id]

              return (
                // Task 3 — group wrapper for tooltip
                <div key={tab.id} className="relative group/tooltip flex-shrink-0">
                  {/* Task 1 — pill tab button */}
                  <button
                    onClick={() => onTabChange(tab.id)}
                    className={`relative flex items-center gap-2 px-3.5 py-2 text-[12.5px] font-medium rounded-lg whitespace-nowrap transition-all duration-200 ${
                      isActive
                        ? 'bg-[#162440] text-white shadow-sm ring-1 ring-blue-500/30'
                        : 'text-[#5a6a85] hover:text-[#a0b4cc] hover:bg-[#111827]/80'
                    }`}
                  >
                    <Icon
                      size={14}
                      className={isActive ? 'text-blue-400' : 'text-current'}
                    />
                    {tab.label}

                    {/* Red dot — live alerts */}
                    {notif === true && (
                      <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500 border-2 border-[#0a0e1a]" />
                    )}
                    {/* Emerald dot — fresh award data */}
                    {notif === 'fresh' && (
                      <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 border-2 border-[#0a0e1a]" />
                    )}
                  </button>

                  {/* Task 3 — hover tooltip, appears below tab */}
                  {tooltip && (
                    <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2.5 z-50
                      opacity-0 group-hover/tooltip:opacity-100 pointer-events-none
                      transition-opacity duration-150
                      w-max max-w-[220px]
                      px-3 py-2 rounded-lg
                      bg-[#0d1526]/95 border border-[#1e2a42]
                      text-[11px] text-[#8896b0] leading-relaxed shadow-xl
                      backdrop-blur-sm">
                      {/* Upward arrow */}
                      <span className="absolute -top-[5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 rotate-45 bg-[#0d1526] border-l border-t border-[#1e2a42]" />
                      {tooltip}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Right-side fade mask on mobile */}
          {!scrolledToEnd && (
            <div className="absolute right-0 top-0 bottom-0 w-10 bg-gradient-to-l from-[#080d18] to-transparent pointer-events-none sm:hidden" />
          )}
        </div>
      </div>
    </div>
  )
}
