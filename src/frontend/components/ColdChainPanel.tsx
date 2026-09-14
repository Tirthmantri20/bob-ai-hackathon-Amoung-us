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
        <div className="flex items-center gap-2 rounded-md bg-red-900/40 border border-red-700 px-3 py-2">
          <span className="text-red-400 font-bold text-sm">🌡 EXCURSION ACTIVE</span>
          <SeverityBadge severity={data.severity} />
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-md bg-green-900/30 border border-green-700 px-3 py-2">
          <span className="text-green-400 font-semibold text-sm">✓ Within Specification</span>
          <SeverityBadge severity={data.severity} />
        </div>
      )}

      {/* Destructive threshold */}
      {data.is_destructive && (
        <div className="rounded-md bg-yellow-900/40 border border-yellow-600 px-3 py-2 text-sm text-yellow-300">
          ⚠ Destructive Threshold Exceeded — cargo may be irreversibly compromised.
        </div>
      )}

      {/* Temperature details */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded bg-gray-800 px-3 py-2">
          <p className="text-xs text-gray-500 mb-1">Cargo Temp</p>
          <p className={`font-mono font-semibold ${data.is_in_excursion ? 'text-orange-400' : 'text-white'}`}>
            {data.cargo_temp_c !== null ? `${data.cargo_temp_c.toFixed(1)}°C` : 'N/A'}
          </p>
        </div>
        <div className="rounded bg-gray-800 px-3 py-2">
          <p className="text-xs text-gray-500 mb-1">Allowed Range</p>
          <p className="font-mono font-semibold text-white">
            {data.allowed_min_c !== null && data.allowed_max_c !== null
              ? `${data.allowed_min_c}°C to ${data.allowed_max_c}°C`
              : 'N/A'}
          </p>
        </div>
        <div className="rounded bg-gray-800 px-3 py-2">
          <p className="text-xs text-gray-500 mb-1">Deviation</p>
          <p className={`font-mono font-bold ${deviationColor}`}>{deviationText}</p>
        </div>
        <div className="rounded bg-gray-800 px-3 py-2">
          <p className="text-xs text-gray-500 mb-1">Grade</p>
          <p className="text-xs font-semibold text-gray-200">{data.grade ?? '—'}</p>
        </div>
      </div>

      {/* Compliance standard */}
      {data.compliance_standard && (
        <p className="text-xs text-blue-400">
          📋 {data.compliance_standard}
        </p>
      )}
    </div>
  )
}
