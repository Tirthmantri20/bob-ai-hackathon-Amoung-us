/**
 * SeverityBadge — colored pill for risk/cold-chain/disruption severity levels.
 * Color is never the sole differentiator; the text label is always present.
 */

interface SeverityBadgeProps {
  severity: string
  size?: 'sm' | 'md'
}

const SEVERITY_CLASSES: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  HIGH:     'bg-orange-500 text-white',
  MEDIUM:   'bg-yellow-400 text-gray-900',
  LOW:      'bg-green-600 text-white',
  OK:       'bg-green-500 text-white',
  WARNING:  'bg-amber-500 text-white',
  UNKNOWN:  'bg-gray-400 text-white',
}

export default function SeverityBadge({ severity, size = 'sm' }: SeverityBadgeProps) {
  const colorClass = SEVERITY_CLASSES[severity?.toUpperCase()] ?? SEVERITY_CLASSES.UNKNOWN
  const sizeClass = size === 'md' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'

  return (
    <span
      className={`inline-flex items-center rounded-full font-bold uppercase tracking-wide ${colorClass} ${sizeClass}`}
      aria-label={`Severity: ${severity}`}
    >
      {severity ?? 'UNKNOWN'}
    </span>
  )
}
