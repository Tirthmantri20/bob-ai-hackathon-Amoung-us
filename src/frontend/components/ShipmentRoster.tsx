import { useState, useMemo } from 'react'
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
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const filteredShipments = useMemo(() => {
    return shipments.filter((shp) => {
      const matchesStatus = statusFilter === 'ALL' || shp.status === statusFilter
      const q = search.trim().toLowerCase()
      if (!q) return matchesStatus

      const matchesQuery =
        shp.id.toLowerCase().includes(q) ||
        (shp.tracking_number && shp.tracking_number.toLowerCase().includes(q)) ||
        shp.cargo_type.toLowerCase().includes(q) ||
        shp.origin.toLowerCase().includes(q) ||
        shp.destination.toLowerCase().includes(q) ||
        (shp.current_location_name && shp.current_location_name.toLowerCase().includes(q))

      return matchesStatus && matchesQuery
    })
  }, [shipments, search, statusFilter])

  if (shipments.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-4 text-center">
        No shipments found.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {/* ── Quick Selector Dropdown & Filter Bar ── */}
      <div className="space-y-2">
        <select
          value={selectedId ?? ''}
          onChange={(e) => {
            if (e.target.value) onSelect(e.target.value)
          }}
          className="w-full text-xs font-semibold rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-slate-700 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-xs"
          aria-label="Quick jump to shipment"
        >
          <option value="" disabled>
            ⚡ Jump to Shipment ({shipments.length} total)...
          </option>
          {shipments.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id} — {s.cargo_type} ({s.origin.split(',')[0]} → {s.destination.split(',')[0]})
            </option>
          ))}
        </select>

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search ID, cargo, city..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 text-xs rounded-lg border border-slate-200 px-2.5 py-1 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Filter shipments by status"
          >
            <option value="ALL">All Status</option>
            <option value="IN_TRANSIT">In Transit</option>
            <option value="ALERT_DISRUPTION">Alert / Disrupted</option>
            <option value="PENDING">Pending</option>
            <option value="DELIVERED">Delivered</option>
          </select>
        </div>
      </div>

      {/* ── Scrollable list with fixed max height ── */}
      <div className="max-h-[360px] overflow-y-auto space-y-2 pr-1">
        {filteredShipments.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-4 italic">
            No matching shipments ({shipments.length} total)
          </p>
        ) : (
          filteredShipments.map((shp) => {
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
                    ? 'border-blue-500 bg-blue-50/80 ring-2 ring-blue-400 shadow-sm'
                    : isCritical
                      ? 'border-red-200 bg-red-50/50 hover:bg-red-50'
                      : 'border-slate-200 bg-white hover:bg-slate-50 shadow-sm',
                ].join(' ')}
                aria-pressed={isSelected}
                aria-label={`Select shipment ${shp.id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-bold text-slate-900">
                        {shp.id}
                      </span>
                      <StatusBadge status={shp.status} />
                      <SeverityBadge severity={severity} />
                    </div>
                    <p className="mt-1 text-xs text-slate-600 font-medium truncate">
                      {shp.cargo_type}
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {shp.origin} &rarr; {shp.destination}
                    </p>
                  </div>
                  {risk && (
                    <div className="text-right shrink-0">
                      <span
                        className={`text-lg font-extrabold tabular-nums ${
                          severity === 'CRITICAL'
                            ? 'text-red-600'
                            : severity === 'HIGH'
                              ? 'text-orange-600'
                              : severity === 'MEDIUM'
                                ? 'text-amber-600'
                                : 'text-emerald-600'
                        }`}
                      >
                        {risk.total_score.toFixed(0)}
                      </span>
                    </div>
                  )}
                </div>
                {shp.current_location_name && (
                  <p className="mt-1 text-xs text-slate-500">
                    📍 {shp.current_location_name}
                  </p>
                )}
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

