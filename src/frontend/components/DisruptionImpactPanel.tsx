'use client'

/**
 * DisruptionImpactPanel — affected shipments within a disruption radius.
 */

import type { Disruption, DisruptionImpact } from '@/services/types'
import LoadingSpinner from './LoadingSpinner'
import SeverityBadge from './SeverityBadge'
import StatusBadge from './StatusBadge'

interface DisruptionImpactPanelProps {
  disruption: Disruption | null
  impact: DisruptionImpact | null
  loading: boolean
  onRequestAIBrief: () => void
}

export default function DisruptionImpactPanel({
  disruption,
  impact,
  loading,
  onRequestAIBrief,
}: DisruptionImpactPanelProps) {
  if (!disruption) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        Select a disruption to view impact.
      </p>
    )
  }

  if (loading) return <LoadingSpinner label="Computing disruption impact…" />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="font-semibold text-white">{disruption.title}</h3>
          <p className="text-xs text-gray-400">{disruption.id}</p>
        </div>
        <SeverityBadge severity={disruption.severity} size="md" />
      </div>

      {impact && (
        <>
          <p className="text-xs text-gray-400">
            Impact radius:{' '}
            <strong className="text-gray-200">{impact.proximity_radius_km} km</strong>
          </p>

          {impact.affected_shipments.length === 0 ? (
            <div className="rounded-md bg-gray-800 border border-gray-700 px-4 py-3 text-sm text-gray-400">
              No active shipments within the {impact.proximity_radius_km} km impact radius.
            </div>
          ) : (
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
                Affected Shipments ({impact.affected_shipments.length})
              </p>
              <div className="space-y-1">
                {impact.affected_shipments.map((s) => (
                  <div
                    key={s.shipment_id}
                    className="flex items-center justify-between rounded bg-gray-800 px-3 py-2 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-white">{s.shipment_id}</span>
                      <StatusBadge status={s.shipment_status} />
                    </div>
                    <span className="text-xs text-gray-400">
                      {s.distance_km.toFixed(0)} km away
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <button
        onClick={onRequestAIBrief}
        className="w-full rounded-lg bg-blue-700 px-4 py-3 text-sm font-semibold text-white
                   hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400
                   transition-colors"
      >
        🤖 Get AI Brief for {disruption.id}
      </button>
    </div>
  )
}
