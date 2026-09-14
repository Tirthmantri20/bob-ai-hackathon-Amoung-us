/**
 * RiskScoreGauge — displays the 0–100 risk score from the engine endpoint.
 *
 * IMPORTANT: `score` MUST come from ShipmentRisk.total_score (0–100).
 * Never pass Shipment.current_risk_score (0–1) to this component.
 */

import type { RiskSeverity } from '@/services/types'

interface RiskScoreGaugeProps {
  /** 0–100 from ShipmentRisk.total_score (engine scale) */
  score: number
  severity: RiskSeverity
}

const GAUGE_BAR_CLASSES: Record<RiskSeverity, string> = {
  CRITICAL: 'bg-red-600',
  HIGH:     'bg-orange-500',
  MEDIUM:   'bg-yellow-400',
  LOW:      'bg-green-600',
}

const SCORE_TEXT_CLASSES: Record<RiskSeverity, string> = {
  CRITICAL: 'text-red-400',
  HIGH:     'text-orange-400',
  MEDIUM:   'text-yellow-400',
  LOW:      'text-green-400',
}

export default function RiskScoreGauge({ score, severity }: RiskScoreGaugeProps) {
  const barClass = GAUGE_BAR_CLASSES[severity] ?? 'bg-gray-500'
  const textClass = SCORE_TEXT_CLASSES[severity] ?? 'text-gray-400'
  const clampedWidth = Math.max(0, Math.min(100, score))

  return (
    <div className="space-y-1">
      <div className="flex items-end justify-between">
        <span className={`text-4xl font-extrabold tabular-nums ${textClass}`}>
          {score.toFixed(1)}
        </span>
        <span className="text-xs text-gray-400 pb-1">/ 100</span>
      </div>
      <div className="h-3 w-full rounded-full bg-gray-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barClass}`}
          style={{ width: `${clampedWidth}%` }}
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Risk score: ${score.toFixed(1)} out of 100`}
        />
      </div>
    </div>
  )
}
