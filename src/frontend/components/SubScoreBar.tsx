/**
 * SubScoreBar — horizontal progress bar for a single 0–1 risk sub-score.
 * Used ×5 in ShipmentDetailPanel (disruption, weather, route, cold_chain, business).
 */

interface SubScoreBarProps {
  label: string
  value: number  // 0–1
  fallback?: boolean
}

export default function SubScoreBar({ label, value, fallback = false }: SubScoreBarProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100

  return (
    <div className="flex items-center gap-2">
      <span className="w-28 shrink-0 text-xs text-slate-600 font-medium">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={1}
          aria-label={`${label}: ${(value * 100).toFixed(0)}%`}
        />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-slate-700 font-semibold">
        {(value * 100).toFixed(0)}%
      </span>
      {fallback && (
        <span className="text-xs text-slate-400 italic" title="Estimated — no data available">
          ⓘ est.
        </span>
      )}
    </div>
  )
}
