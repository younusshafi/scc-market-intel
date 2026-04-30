export default function BriefingCard({ briefing }) {
  return (
    <div
      className="bg-[#1E293B] border border-[#334155] rounded-xl p-6"
      style={{ borderTop: '3px solid transparent', borderImage: 'linear-gradient(to right, #3b82f6, #8b5cf6) 1', borderImageSlice: '1 1 0 0' }}
    >
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">
          AI Executive Briefing
        </h3>
        <span className="text-[10px] font-semibold bg-cyan-500/15 text-cyan-400 px-2.5 py-0.5 rounded-full uppercase tracking-wider">
          AI Generated
        </span>
      </div>

      {briefing ? (
        <>
          {briefing.title && (
            <h2 className="text-[15px] font-bold text-white mb-3">{briefing.title}</h2>
          )}
          <div
            className="prose prose-invert prose-sm max-w-none
              prose-headings:text-white prose-headings:text-sm prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-1
              prose-p:text-[#e8ecf4] prose-p:leading-relaxed prose-p:text-sm
              prose-li:text-[#e8ecf4] prose-strong:text-white"
            dangerouslySetInnerHTML={{ __html: briefing.content_html || formatMd(briefing.content_md) }}
          />
          <p className="text-[11px] text-[#5a6a85] mt-4">
            Generated {new Date(briefing.generated_at).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'long', year: 'numeric'
            })}
          </p>
        </>
      ) : (
        <p className="text-sm text-[#5a6a85] italic">No briefing available yet.</p>
      )}
    </div>
  )
}

function formatMd(md) {
  if (!md) return ''
  return md
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hulo])/gm, '<p>')
}
