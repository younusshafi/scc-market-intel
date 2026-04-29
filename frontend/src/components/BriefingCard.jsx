export default function BriefingCard({ briefing }) {
  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6 border-t-[3px] border-t-blue-500">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          AI Executive Briefing
        </h3>
        <span className="text-[10px] font-semibold bg-cyan-500/15 text-cyan-400 px-2.5 py-0.5 rounded-full uppercase tracking-wider">
          AI Generated
        </span>
      </div>

      {briefing ? (
        <>
          <div
            className="prose prose-invert prose-sm max-w-none
              prose-headings:text-white prose-headings:text-sm prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-1
              prose-p:text-slate-300 prose-p:leading-relaxed prose-p:text-sm
              prose-li:text-slate-300 prose-strong:text-white"
            dangerouslySetInnerHTML={{ __html: briefing.content_html || formatMd(briefing.content_md) }}
          />
          <p className="text-[11px] text-slate-500 mt-4">
            Generated {new Date(briefing.generated_at).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'long', year: 'numeric'
            })}
          </p>
        </>
      ) : (
        <p className="text-sm text-slate-500 italic">No briefing available yet. The first will generate on Sunday.</p>
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
