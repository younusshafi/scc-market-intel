import { useRef, useState } from 'react'
import { LayoutDashboard, Swords, Target, Newspaper, UserSearch, BarChart2 } from 'lucide-react'

const TABS = [
  { id: 'command-centre',  label: 'Command Centre',    icon: LayoutDashboard },
  { id: 'competitive-intel', label: 'Competitive Intel', icon: Swords },
  { id: 'opportunities',   label: 'Opportunities',      icon: Target },
  { id: 'award-intel',     label: 'Award Intelligence', icon: BarChart2 },
  { id: 'market-news',     label: 'Market & News',      icon: Newspaper },
  { id: 'profiles',        label: 'Profiles',           icon: UserSearch },
]

export default function TabNavigation({ activeTab, onTabChange, notifications = {} }) {
  const tabRef = useRef(null)
  const [scrolledToEnd, setScrolledToEnd] = useState(false)

  function handleScroll(e) {
    const el = e.target
    setScrolledToEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4)
  }

  return (
    <div className="sticky top-[57px] z-40 bg-[#0f1525] border-b border-[#1e2a42]">
      <div className="max-w-[1400px] mx-auto">
        {/* Relative wrapper for the fade mask */}
        <div className="relative px-4 sm:px-8">
          <div
            ref={tabRef}
            className="flex gap-1 overflow-x-auto"
            style={{ scrollbarWidth: 'none' }}
            onScroll={handleScroll}
          >
            {TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              const notif = notifications[tab.id]

              return (
                <button
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  className={`relative flex items-center gap-2 px-4 py-3 text-[13px] font-medium uppercase tracking-[0.05em] whitespace-nowrap transition-colors duration-150 border-b-2 flex-shrink-0 ${
                    isActive
                      ? 'text-[#e8ecf4] border-[#3b82f6]'
                      : 'text-[#5a6a85] border-transparent hover:text-[#8896b0]'
                  }`}
                >
                  <Icon size={16} />
                  {tab.label}

                  {/* Red dot — live competitive / news alerts */}
                  {notif === true && (
                    <span className="absolute -top-0.5 right-1 w-2 h-2 rounded-full bg-red-500 border border-[#0f1525]" />
                  )}

                  {/* Emerald dot — award data freshly computed */}
                  {notif === 'fresh' && (
                    <span className="absolute -top-0.5 right-1 w-2 h-2 rounded-full bg-emerald-400 border border-[#0f1525]" />
                  )}
                </button>
              )
            })}
          </div>

          {/* Right-side fade mask — disappears when scrolled to end */}
          {!scrolledToEnd && (
            <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-[#0f1525] to-transparent pointer-events-none sm:hidden" />
          )}
        </div>
      </div>
    </div>
  )
}
