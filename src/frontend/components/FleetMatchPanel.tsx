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
      <p className="text-sm text-gray-500 py-4 text-center">
        No fleet match data available.
      </p>
    )
  }

  if (data.no_asset_found) {
    return (
      <div className="rounded-md bg-gray-800 border border-gray-700 px-4 py-3 text-sm text-gray-400">
        <p className="font-semibold text-gray-300 mb-1">No Alternative Assets Available</p>
        <p>No eligible fleet assets found for emergency reassignment to this shipment.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {data.scored_assets.map((asset) => (
        <div
          key={asset.asset_id}
          className={`rounded-lg border px-4 py-3 ${
            asset.recommended
              ? 'border-green-600 bg-green-900/20'
              : 'border-gray-700 bg-gray-800/50'
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div>
              <span className="font-mono text-sm font-bold text-white">{asset.asset_id}</span>
              <span className="ml-2 text-xs text-gray-400">{asset.vehicle_type}</span>
            </div>
            <div className="flex items-center gap-2">
              {asset.recommended && (
                <span className="rounded-full bg-green-700 px-2 py-0.5 text-xs font-bold text-white">
                  ⭐ Top Match
                </span>
              )}
              <span className="text-sm font-bold tabular-nums text-blue-300">
                {(asset.total_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-400">
            <span className="font-medium text-gray-300">
              {COOLING_LABELS[asset.cooling_capability] ?? asset.cooling_capability}
            </span>
            <span>
              Proximity:{' '}
              <strong className="text-gray-200">
                {asset.proximity_km !== null ? `${asset.proximity_km.toFixed(0)} km` : 'N/A'}
              </strong>
            </span>
            <span>
              Compat:{' '}
              <strong className="text-gray-200">
                {(asset.cargo_compat_score * 100).toFixed(0)}%
              </strong>
            </span>
            <span>
              Refrig:{' '}
              <strong className="text-gray-200">
                {(asset.refrigeration_score * 100).toFixed(0)}%
              </strong>
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
