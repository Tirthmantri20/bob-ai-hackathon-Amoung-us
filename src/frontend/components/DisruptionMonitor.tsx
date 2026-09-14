'use client'

/**
 * DisruptionMonitor — list of all active disruptions.
 * Clicking a card triggers onSelect with the disruption ID.
 */

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
  SEVERE_WEATHER:      '🌨 Severe Weather',
  PORT_CONTAINER_HOLD: '⚓ Port Hold',
  ROADWORK_CONGESTION: '🚧 Roadwork',
}

export default function DisruptionMonitor({
  disruptions,
  selectedId,
  onSelect,
}: DisruptionMonitorProps) {
  if (disruptions.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        No active disruptions.
      </p>
    )
  }

  const sorted = [...disruptions].sort((a, b) => {
    const ao = SEVERITY_ORDER[a.severity?.toUpperCase()] ?? 99
    const bo = SEVERITY_ORDER[b.severity?.toUpperCase()] ?? 99
    return ao - bo
  })

  return (
    <div className="space-y-2">
      {sorted.map((dis) => {
        const isSelected = dis.id === selectedId
        return (
          <button
            key={dis.id}
            onClick={() => onSelect(dis.id)}
            className={[
              'w-full text-left rounded-lg border p-3 transition-all',
              'focus:outline-none focus:ring-2 focus:ring-blue-500',
              isSelected
                ? 'border-blue-500 bg-blue-900/30'
                : 'border-gray-700 bg-gray-800/50 hover:bg-gray-800',
            ].join(' ')}
            aria-pressed={isSelected}
            aria-label={`Select disruption ${dis.id}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-semibold text-gray-400">{dis.id}</span>
                  <SeverityBadge severity={dis.severity} />
                </div>
                <p className="mt-1 text-sm font-semibold text-white truncate">
                  {dis.title}
                </p>
                <p className="text-xs text-gray-400">
                  {TYPE_LABELS[dis.type] ?? dis.type}
                </p>
              </div>
            </div>
            {dis.affected_corridor && (
              <p className="mt-1 text-xs text-gray-500">🛣 {dis.affected_corridor}</p>
            )}
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
              {dis.impact_delay_hours !== null && (
                <span>⏱ +{dis.impact_delay_hours} hr delay</span>
              )}
              {dis.recommended_reroute && (
                <span className="italic text-blue-400">↪ {dis.recommended_reroute}</span>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
