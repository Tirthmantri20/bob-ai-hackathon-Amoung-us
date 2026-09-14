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
      <p className="text-sm text-slate-500 py-6 text-center">
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
    <div className="space-y-5">
      {/* Shipment metadata */}
      <div className="border-b border-slate-200 pb-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-xl font-extrabold text-slate-900 font-mono tracking-tight">{shipment.id}</h2>
            <p className="text-sm text-slate-600 font-medium">{shipment.cargo_type} &bull; {shipment.cargo_category}</p>
          </div>
          {risk && <SeverityBadge severity={risk.severity} size="md" />}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2.5 text-xs">
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <span className="text-slate-500 block">From</span>
            <strong className="text-slate-900 text-sm font-semibold">{shipment.origin}</strong>
          </div>
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <span className="text-slate-500 block">To</span>
            <strong className="text-slate-900 text-sm font-semibold">{shipment.destination}</strong>
          </div>
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <span className="text-slate-500 block">Carrier</span>
            <strong className="text-slate-900 font-semibold">{carrierName}</strong>
          </div>
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <span className="text-slate-500 block">Estimated Arrival</span>
            <strong className="text-slate-900 font-semibold">{arrivalDate}</strong>
          </div>
        </div>
        {shipment.current_location_name && (
          <p className="mt-2 text-xs text-slate-500">
            📍 Currently at <strong className="text-slate-700">{shipment.current_location_name}</strong>
          </p>
        )}
      </div>

      {/* Risk score + sub-scores */}
      {risk ? (
        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 space-y-4 shadow-sm">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Composite Risk Score (0–100)
            </p>
            <RiskScoreGauge score={risk.total_score} severity={risk.severity} />
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
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
            <div className="border-t border-slate-200 pt-3">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                Contributing Disruptions
              </p>
              <div className="flex flex-wrap gap-1.5">
                {risk.contributing_disruption_ids.map((d) => (
                  <span
                    key={d}
                    className="rounded-md bg-red-50 border border-red-200 px-2 py-0.5 text-xs font-mono font-bold text-red-700"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-500">Risk data unavailable.</p>
      )}

      {/* Cold-chain */}
      <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Cold Chain Status
        </p>
        <ColdChainPanel data={coldChain} loading={false} />
      </div>

      {/* Route recommendations */}
      <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Route Optimization
        </p>
        <RoutePanel data={routes} loading={false} />
      </div>

      {/* Fleet match */}
      <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Fleet Rescue Candidates
        </p>
        <FleetMatchPanel data={fleetMatch} loading={false} />
      </div>

      {/* AI brief trigger */}
      <button
        onClick={onRequestAIBrief}
        className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white
                   hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400
                   shadow-sm transition-all"
        aria-label={`Get AI Brief for ${shipment.id}`}
      >
        🤖 Get AI Brief for {shipment.id}
      </button>
    </div>
  )
}
