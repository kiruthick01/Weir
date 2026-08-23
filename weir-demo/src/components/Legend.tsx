export function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-3 font-mono text-[11px] uppercase tracking-wide text-muted">
      <span className="font-sans font-bold text-ink">Legend</span>
      <span>normal</span>
      <span className="font-bold">elevated</span>
      <span className="font-bold text-accent">critical</span>
      <span className="text-line">|</span>
      <span>queued</span>
      <span>delegated</span>
      <span>auto approved</span>
      <span className="text-accent">rejected proposal</span>
    </div>
  )
}
