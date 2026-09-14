'use client'

/**
 * FleetMatchPanel — ranked fleet asset recommendations.
 */

import type { FleetMatch } from '@/services/types'
import LoadingSpinner from './LoadingSpinner'

interface FleetMatchPanelProps {
  data: FleetMatch | null
  loading: boolean
}

const COOLING_LABELS: Record<string, string> = {
  ULTRA_COLD:    '🧊 Ultra-Cold',
  STANDARD_COLD: '❄ Standard Cold',
  AMBIENT:       '🌡 Ambient',
}

export default function FleetMatchPanel({ data, loading }: FleetMatchPanelProps) {
  if (loading) return <LoadingSpinner label="Matching fleet assets…" />

  if (!data) {
    return (
      <p className="text-sm text-slate-500 py-4 text-center">
        No fleet match data available.
      </p>
    )
  }

  if (data.no_asset_found) {
    return (
      <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-sm text-slate-600">
        <p className="font-semibold text-slate-800 mb-1">No Alternative Assets Available</p>
        <p>No eligible fleet assets found for emergency reassignment to this shipment.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {data.scored_assets.map((asset) => (
        <div
          key={asset.asset_id}
          className={`rounded-lg border px-4 py-3 shadow-sm ${
            asset.recommended
              ? 'border-emerald-300 bg-emerald-50/70'
              : 'border-slate-200 bg-white'
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div>
              <span className="font-mono text-sm font-bold text-slate-900">{asset.asset_id}</span>
              <span className="ml-2 text-xs text-slate-500 font-medium">{asset.vehicle_type}</span>
            </div>
            <div className="flex items-center gap-2">
              {asset.recommended && (
                <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs font-bold text-white shadow-xs">
                  ⭐ Top Match
                </span>
              )}
              <span className="text-sm font-extrabold tabular-nums text-blue-700">
                {(asset.total_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
            <span className="font-semibold text-slate-700">
              {COOLING_LABELS[asset.cooling_capability] ?? asset.cooling_capability}
            </span>
            <span>
              Proximity:{' '}
              <strong className="text-slate-800">
                {asset.proximity_km !== null ? `${asset.proximity_km.toFixed(0)} km` : 'N/A'}
              </strong>
            </span>
            <span>
              Compat:{' '}
              <strong className="text-slate-800">
                {(asset.cargo_compat_score * 100).toFixed(0)}%
              </strong>
            </span>
            <span>
              Refrig:{' '}
              <strong className="text-slate-800">
                {(asset.refrigeration_score * 100).toFixed(0)}%
              </strong>
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
