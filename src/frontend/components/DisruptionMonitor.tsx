import { useState, useMemo } from 'react'
import type { Disruption } from '@/services/types'
import SeverityBadge from './SeverityBadge'

interface DisruptionMonitorProps {
  disruptions: Disruption[]
  selectedId: string | null
  onSelect: (id: string) => void
}

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
}

const TYPE_LABELS: Record<string, string> = {
  SEVERE_WEATHER: '🌨 Severe Weather',
  PORT_CONTAINER_HOLD: '⚓ Port Hold',
  ROADWORK_CONGESTION: '🚧 Roadwork',
}

export default function DisruptionMonitor({
  disruptions,
  selectedId,
  onSelect,
}: DisruptionMonitorProps) {
  const [severityFilter, setSeverityFilter] = useState('ALL')

  const sorted = useMemo(() => {
    const list = [...disruptions].sort((a, b) => {
      const ao = SEVERITY_ORDER[a.severity?.toUpperCase()] ?? 99
      const bo = SEVERITY_ORDER[b.severity?.toUpperCase()] ?? 99
      return ao - bo
    })
    if (severityFilter === 'ALL') return list
    return list.filter((d) => d.severity?.toUpperCase() === severityFilter)
  }, [disruptions, severityFilter])

  if (disruptions.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-4 text-center">
        No active disruptions.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {/* ── Quick Selector Dropdown & Filter Bar ── */}
      <div className="flex gap-2">
        <select
          value={selectedId ?? ''}
          onChange={(e) => {
            if (e.target.value) onSelect(e.target.value)
          }}
          className="flex-1 text-xs font-semibold rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-slate-700 focus:border-amber-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-500 shadow-xs"
          aria-label="Quick jump to disruption"
        >
          <option value="" disabled>
            ⚠️ Jump to Disruption ({disruptions.length} total)...
          </option>
          {disruptions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.id} — [{d.severity}] {d.title}
            </option>
          ))}
        </select>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-xs rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
          aria-label="Filter disruptions by severity"
        >
          <option value="ALL">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* ── Scrollable list with fixed max height ── */}
      <div className="max-h-[300px] overflow-y-auto space-y-2 pr-1">
        {sorted.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-4 italic">
            No matching disruptions
          </p>
        ) : (
          sorted.map((dis) => {
            const isSelected = dis.id === selectedId
            return (
              <button
                key={dis.id}
                onClick={() => onSelect(dis.id)}
                className={[
                  'w-full text-left rounded-lg border p-3 transition-all',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500',
                  isSelected
                    ? 'border-blue-500 bg-blue-50/80 ring-2 ring-blue-400 shadow-sm'
                    : 'border-slate-200 bg-white hover:bg-slate-50 shadow-sm',
                ].join(' ')}
                aria-pressed={isSelected}
                aria-label={`Select disruption ${dis.id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-slate-700">{dis.id}</span>
                      <SeverityBadge severity={dis.severity} />
                    </div>
                    <p className="mt-1 text-sm font-semibold text-slate-900 truncate">
                      {dis.title}
                    </p>
                    <p className="text-xs text-slate-600">
                      {TYPE_LABELS[dis.type] ?? dis.type}
                    </p>
                  </div>
                </div>
                {dis.affected_corridor && (
                  <p className="mt-1 text-xs text-slate-500">🛣 {dis.affected_corridor}</p>
                )}
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500 font-medium">
                  {dis.impact_delay_hours !== null && (
                    <span>⏱ +{dis.impact_delay_hours} hr delay</span>
                  )}
                  {dis.recommended_reroute && (
                    <span className="italic text-blue-600">↪ {dis.recommended_reroute}</span>
                  )}
                </div>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

