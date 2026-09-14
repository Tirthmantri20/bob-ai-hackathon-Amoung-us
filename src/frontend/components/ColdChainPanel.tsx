'use client'

/**
 * ColdChainPanel — excursion state, temperature deviation, and compliance.
 */

import type { ColdChainStatus } from '@/services/types'
import LoadingSpinner from './LoadingSpinner'
import SeverityBadge from './SeverityBadge'

interface ColdChainPanelProps {
  data: ColdChainStatus | null
  loading: boolean
}

export default function ColdChainPanel({ data, loading }: ColdChainPanelProps) {
  if (loading) return <LoadingSpinner label="Evaluating cold chain…" />

  if (!data) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        No cold-chain data available.
      </p>
    )
  }

  if (!data.cargo_rule_found) {
    return (
      <p className="text-sm text-yellow-500 py-2">
        ⚠ No cargo rule configured for this cargo category.
      </p>
    )
  }

  const deviationText = (() => {
    if (data.deviation_c === null) return 'N/A'
    const sign = data.deviation_c >= 0 ? '+' : ''
    return `${sign}${data.deviation_c.toFixed(1)}°C`
  })()

  const deviationColor =
    data.deviation_c === null
      ? 'text-gray-400'
      : data.is_destructive
        ? 'text-red-400'
        : data.is_in_excursion
          ? 'text-orange-400'
          : 'text-green-400'

  return (
    <div className="space-y-3">
      {/* Excursion banner */}
      {data.is_in_excursion ? (
        <div className="flex items-center justify-between gap-2 rounded-lg bg-red-50 border border-red-200 px-3.5 py-2.5 shadow-sm">
          <span className="text-red-700 font-bold text-sm">🌡 EXCURSION ACTIVE</span>
          <SeverityBadge severity={data.severity} />
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-3.5 py-2.5 shadow-sm">
          <span className="text-emerald-700 font-semibold text-sm">✓ Within Specification</span>
          <SeverityBadge severity={data.severity} />
        </div>
      )}

      {/* Destructive threshold */}
      {data.is_destructive && (
        <div className="rounded-lg bg-amber-50 border border-amber-300 px-3.5 py-2 text-sm text-amber-900 font-medium">
          ⚠ Destructive Threshold Exceeded — cargo may be irreversibly compromised.
        </div>
      )}

      {/* Temperature details */}
      <div className="grid grid-cols-2 gap-2.5 text-sm">
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 shadow-sm">
          <p className="text-xs text-slate-500 mb-1 font-medium">Cargo Temp</p>
          <p className={`font-mono font-bold ${data.is_in_excursion ? 'text-orange-600' : 'text-slate-900'}`}>
            {data.cargo_temp_c !== null ? `${data.cargo_temp_c.toFixed(1)}°C` : 'N/A'}
          </p>
        </div>
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 shadow-sm">
          <p className="text-xs text-slate-500 mb-1 font-medium">Allowed Range</p>
          <p className="font-mono font-bold text-slate-900">
            {data.allowed_min_c !== null && data.allowed_max_c !== null
              ? `${data.allowed_min_c}°C to ${data.allowed_max_c}°C`
              : 'N/A'}
          </p>
        </div>
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 shadow-sm">
          <p className="text-xs text-slate-500 mb-1 font-medium">Deviation</p>
          <p className={`font-mono font-bold ${deviationColor}`}>{deviationText}</p>
        </div>
        <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 shadow-sm">
          <p className="text-xs text-slate-500 mb-1 font-medium">Grade</p>
          <p className="text-xs font-bold text-slate-800">{data.grade ?? '—'}</p>
        </div>
      </div>

      {/* Compliance standard */}
      {data.compliance_standard && (
        <p className="text-xs text-blue-700 font-medium">
          📋 Standard: {data.compliance_standard}
        </p>
      )}
    </div>
  )
}
