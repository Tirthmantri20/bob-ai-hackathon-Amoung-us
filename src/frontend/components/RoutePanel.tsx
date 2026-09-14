'use client'

/**
 * RoutePanel — ranked route recommendations from the optimizer.
 * Honest representation of no_route_found state.
 */

import type { RouteRecommendation } from '@/services/types'
import LoadingSpinner from './LoadingSpinner'

interface RoutePanelProps {
  data: RouteRecommendation | null
  loading: boolean
}

export default function RoutePanel({ data, loading }: RoutePanelProps) {
  if (loading) return <LoadingSpinner label="Computing routes…" />

  if (!data) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        No route data available.
      </p>
    )
  }

  if (data.no_route_found) {
    return (
      <div className="rounded-md bg-gray-800 border border-gray-700 px-4 py-3 text-sm text-gray-400">
        <p className="font-semibold text-gray-300 mb-1">No Route Match Found</p>
        <p>
          The route optimizer requires an exact origin/destination match in the
          route catalog. No route is configured for this shipment corridor.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {data.scored_routes.map((route) => (
        <div
          key={route.route_id}
          className={`rounded-lg border px-4 py-3 ${
            route.recommended
              ? 'border-green-600 bg-green-900/20'
              : 'border-gray-700 bg-gray-800/50'
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-sm font-semibold text-white">{route.route_name}</span>
            <div className="flex items-center gap-2">
              {route.recommended && (
                <span className="rounded-full bg-green-700 px-2 py-0.5 text-xs font-bold text-white">
                  ⭐ Recommended
                </span>
              )}
              <span className="text-sm font-bold tabular-nums text-blue-300">
                {(route.total_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-400">
            <span>ETA: <strong className="text-gray-200">{route.eta_hours.toFixed(1)} hr</strong></span>
            <span>Disruption: <strong className="text-gray-200">{(route.disruption_factor * 100).toFixed(0)}%</strong></span>
            <span>Weather: <strong className="text-gray-200">{(route.weather_factor * 100).toFixed(0)}%</strong></span>
          </div>

          {route.warnings.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {route.warnings.map((w, i) => (
                <span
                  key={i}
                  className="rounded-full bg-yellow-900/50 border border-yellow-700 px-2 py-0.5 text-xs text-yellow-300"
                >
                  ⚠ {w}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
