/**
 * StatusBadge — colored pill for shipment status and fleet asset status.
 */

interface StatusBadgeProps {
  status: string
}

const STATUS_CLASSES: Record<string, string> = {
  IDLE:               'bg-green-600 text-white',
  ACTIVE:             'bg-blue-500 text-white',
  EN_ROUTE:           'bg-purple-500 text-white',
  IN_TRANSIT:         'bg-blue-400 text-white',
  ALERT_DISRUPTION:   'bg-red-600 text-white',
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colorClass = STATUS_CLASSES[status?.toUpperCase()] ?? 'bg-gray-400 text-white'
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${colorClass}`}
      aria-label={`Status: ${status}`}
    >
      {status ?? '—'}
    </span>
  )
}
