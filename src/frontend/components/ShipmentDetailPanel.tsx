'use client'

/**
 * ShipmentDetailPanel — full operational picture for a selected shipment.
 * Assembles: metadata, risk gauge, 5 sub-score bars, cold-chain,
 * route recommendations, fleet match, and AI brief trigger.
 */

import type { ColdChainStatus, FleetMatch, RouteRecommendation, Shipment, ShipmentRisk } from '@/services/types'
import { CARRIER_NAMES } from '@/services/types'
import ColdChainPanel from './ColdChainPanel'
import FleetMatchPanel from './FleetMatchPanel'
import LoadingSpinner from './LoadingSpinner'
import RiskScoreGauge from './RiskScoreGauge'
import RoutePanel from './RoutePanel'
import SeverityBadge from './SeverityBadge'
import SubScoreBar from './SubScoreBar'

interface ShipmentDetailPanelProps {
  shipment: Shipment | null
  risk: ShipmentRisk | null
  coldChain: ColdChainStatus | null
  routes: RouteRecommendation | null
  fleetMatch: FleetMatch | null
  loading: boolean
  onRequestAIBrief: () => void
}

export default function ShipmentDetailPanel({
  shipment,
  risk,
  coldChain,
  routes,
  fleetMatch,
  loading,
  onRequestAIBrief,
}: ShipmentDetailPanelProps) {
  if (!shipment) {
    return (
      <p className="text-sm text-gray-500 py-6 text-center">
        Select a shipment from the roster to view details.
      </p>
    )
  }

  if (loading) {
    return <LoadingSpinner label="Loading shipment details…" />
  }

  const carrierName = shipment.carrier_id
    ? (CARRIER_NAMES[shipment.carrier_id] ?? shipment.carrier_id)
    : '—'

  const arrivalDate = shipment.estimated_arrival
    ? new Date(shipment.estimated_arrival).toLocaleString()
    : '—'

  return (
    <div className="space-y-6">
      {/* Shipment metadata */}
      <div>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-bold text-white font-mono">{shipment.id}</h2>
            <p className="text-sm text-gray-400">{shipment.cargo_type} — {shipment.cargo_category}</p>
          </div>
          {risk && <SeverityBadge severity={risk.severity} size="md" />}
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400">
          <span>From: <strong className="text-gray-200">{shipment.origin}</strong></span>
          <span>To: <strong className="text-gray-200">{shipment.destination}</strong></span>
          <span>ETA: <strong className="text-gray-200">{arrivalDate}</strong></span>
          <span>Carrier: <strong className="text-gray-200">{carrierName}</strong></span>
        </div>
        {shipment.current_location_name && (
          <p className="mt-1 text-xs text-gray-500">
            📍 Currently at {shipment.current_location_name}
          </p>
        )}
      </div>

      {/* Risk score + sub-scores */}
      {risk ? (
        <div className="rounded-lg bg-gray-800 border border-gray-700 p-4 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              Composite Risk Score (0–100)
            </p>
            {/* RiskScoreGauge receives total_score (0–100) from the engine */}
            <RiskScoreGauge score={risk.total_score} severity={risk.severity} />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              Risk Sub-scores
            </p>
            <div className="space-y-2">
              <SubScoreBar label="Disruption" value={risk.r_disruption} />
              <SubScoreBar label="Weather" value={risk.r_weather} fallback={risk.weather_fallback} />
              <SubScoreBar label="Route" value={risk.r_route} fallback={risk.route_fallback} />
              <SubScoreBar label="Cold Chain" value={risk.r_cold_chain} fallback={risk.cold_chain_fallback} />
              <SubScoreBar label="Business" value={risk.r_business} />
            </div>
          </div>

          {risk.contributing_disruption_ids.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-1">
                Contributing Disruptions
              </p>
              <div className="flex flex-wrap gap-1">
                {risk.contributing_disruption_ids.map((d) => (
                  <span
                    key={d}
                    className="rounded bg-red-900/50 border border-red-700 px-2 py-0.5 text-xs font-mono text-red-300"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500">Risk data unavailable.</p>
      )}

      {/* Cold-chain */}
      <div className="rounded-lg bg-gray-800 border border-gray-700 p-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
          Cold Chain Status
        </p>
        <ColdChainPanel data={coldChain} loading={false} />
      </div>

      {/* Route recommendations */}
      <div className="rounded-lg bg-gray-800 border border-gray-700 p-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
          Route Optimization
        </p>
        <RoutePanel data={routes} loading={false} />
      </div>

      {/* Fleet match */}
      <div className="rounded-lg bg-gray-800 border border-gray-700 p-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
          Fleet Rescue Candidates
        </p>
        <FleetMatchPanel data={fleetMatch} loading={false} />
      </div>

      {/* AI brief trigger */}
      <button
        onClick={onRequestAIBrief}
        className="w-full rounded-lg bg-blue-700 px-4 py-3 text-sm font-semibold text-white
                   hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400
                   transition-colors"
      >
        🤖 Get AI Brief for {shipment.id}
      </button>
    </div>
  )
}
