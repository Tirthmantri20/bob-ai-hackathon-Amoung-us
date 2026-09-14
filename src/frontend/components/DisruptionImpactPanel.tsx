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
      <p className="text-sm text-slate-500 py-4 text-center">
        Select a disruption to view impact.
      </p>
    )
  }

  if (loading) return <LoadingSpinner label="Computing disruption impact…" />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-200 pb-3">
        <div>
          <h3 className="font-bold text-slate-900 text-base">{disruption.title}</h3>
          <p className="text-xs text-slate-500 font-mono font-medium">{disruption.id}</p>
        </div>
        <SeverityBadge severity={disruption.severity} size="md" />
      </div>

      {impact && (
        <>
          <p className="text-xs text-slate-600 font-medium">
            Proximity Impact Radius:{' '}
            <strong className="text-slate-900 font-bold">{impact.proximity_radius_km} km</strong>
          </p>

          {impact.affected_shipments.length === 0 ? (
            <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 text-sm text-slate-600">
              No active shipments currently intersect the {impact.proximity_radius_km} km impact radius.
            </div>
          ) : (
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Affected Shipments ({impact.affected_shipments.length})
              </p>
              <div className="space-y-1.5">
                {impact.affected_shipments.map((s) => (
                  <div
                    key={s.shipment_id}
                    className="flex items-center justify-between rounded-lg bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-sm shadow-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-slate-900">{s.shipment_id}</span>
                      <StatusBadge status={s.shipment_status} />
                    </div>
                    <span className="text-xs text-slate-500 font-semibold">
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
        className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white
                   hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400
                   shadow-sm transition-all"
        aria-label={`Get AI Brief for ${disruption.id}`}
      >
        🤖 Get AI Brief for {disruption.id}
      </button>
    </div>
  )
}
