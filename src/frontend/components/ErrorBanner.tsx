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
      className="flex items-center gap-3 rounded-lg border border-red-500 bg-red-900/30 p-4 text-red-300"
      role="alert"
    >
      <span className="text-lg" aria-hidden="true">⚠</span>
      <span className="flex-1 text-sm">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded bg-red-700 px-3 py-1 text-xs font-semibold text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-400"
        >
          Retry
        </button>
      )}
    </div>
  )
}
