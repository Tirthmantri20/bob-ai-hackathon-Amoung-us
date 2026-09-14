/**
 * ErrorBanner — surface backend/network errors with an optional retry.
 */

interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 shadow-sm"
      role="alert"
    >
      <span className="text-xl" aria-hidden="true">⚠</span>
      <span className="flex-1 text-sm font-medium">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-400 shadow-xs"
        >
          Retry
        </button>
      )}
    </div>
  )
}
