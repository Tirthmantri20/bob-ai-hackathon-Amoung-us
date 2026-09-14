'use client'

/**
 * ShipmentRoster — list of all shipments with severity badges.
 * Clicking a row triggers onSelect with the shipment ID.
 */

import type { Shipment, ShipmentRisk } from '@/services/types'
import SeverityBadge from './SeverityBadge'
import StatusBadge from './StatusBadge'

interface ShipmentRosterProps {
  shipments: Shipment[]
  activeRisks: Map<string, ShipmentRisk>
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function ShipmentRoster({
  shipments,
  activeRisks,
  selectedId,
  onSelect,
}: ShipmentRosterProps) {
  if (shipments.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        No shipments found.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {shipments.map((shp) => {
        const risk = activeRisks.get(shp.id)
        const severity = risk?.severity ?? 'UNKNOWN'
        const isSelected = shp.id === selectedId
        const isCritical = severity === 'CRITICAL'

        return (
          <button
            key={shp.id}
            onClick={() => onSelect(shp.id)}
            className={[
              'w-full text-left rounded-lg border p-3 transition-all',
              'focus:outline-none focus:ring-2 focus:ring-blue-500',
              isSelected
                ? 'border-blue-500 bg-blue-900/30'
                : isCritical
                  ? 'border-red-700 bg-red-900/20 hover:bg-red-900/30'
                  : 'border-gray-700 bg-gray-800/50 hover:bg-gray-800',
            ].join(' ')}
            aria-pressed={isSelected}
            aria-label={`Select shipment ${shp.id}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-semibold text-white">
                    {shp.id}
                  </span>
                  <StatusBadge status={shp.status} />
                  <SeverityBadge severity={severity} />
                </div>
                <p className="mt-1 text-xs text-gray-400 truncate">
                  {shp.cargo_type}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {shp.origin} → {shp.destination}
                </p>
              </div>
              {risk && (
                <div className="text-right shrink-0">
                  <span
                    className={`text-lg font-extrabold tabular-nums ${
                      severity === 'CRITICAL' ? 'text-red-400' :
                      severity === 'HIGH' ? 'text-orange-400' :
                      severity === 'MEDIUM' ? 'text-yellow-400' : 'text-green-400'
                    }`}
                  >
                    {risk.total_score.toFixed(0)}
                  </span>
                </div>
              )}
            </div>
            {shp.current_location_name && (
              <p className="mt-1 text-xs text-gray-500">
                📍 {shp.current_location_name}
              </p>
            )}
          </button>
        )
      })}
    </div>
  )
}
