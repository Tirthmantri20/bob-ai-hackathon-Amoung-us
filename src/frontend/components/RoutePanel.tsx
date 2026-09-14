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
      <p className="text-sm text-slate-500 py-4 text-center">
        No route data available.
      </p>
    )
  }

  if (data.no_route_found) {
    return (
      <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-sm text-slate-600">
        <p className="font-semibold text-slate-800 mb-1">No Route Match Found</p>
        <p>
          The route optimizer requires an exact origin/destination match in the
          route catalog. No route is configured for this shipment corridor.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {data.scored_routes.map((route) => (
        <div
          key={route.route_id}
          className={`rounded-lg border px-4 py-3 shadow-sm ${
            route.recommended
              ? 'border-emerald-300 bg-emerald-50/70'
              : 'border-slate-200 bg-white'
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-sm font-bold text-slate-900">{route.route_name}</span>
            <div className="flex items-center gap-2">
              {route.recommended && (
                <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs font-bold text-white shadow-xs">
                  ⭐ Recommended
                </span>
              )}
              <span className="text-sm font-extrabold tabular-nums text-blue-700">
                {(route.total_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
            <span>ETA: <strong className="text-slate-800">{route.eta_hours.toFixed(1)} hr</strong></span>
            <span>Disruption Factor: <strong className="text-slate-800">{(route.disruption_factor * 100).toFixed(0)}%</strong></span>
            <span>Weather Factor: <strong className="text-slate-800">{(route.weather_factor * 100).toFixed(0)}%</strong></span>
          </div>

          {route.warnings.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {route.warnings.map((w, i) => (
                <span
                  key={i}
                  className="rounded-full bg-amber-100 border border-amber-300 px-2 py-0.5 text-xs font-medium text-amber-800"
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
