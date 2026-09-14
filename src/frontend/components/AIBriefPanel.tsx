'use client'

/**
 * AIBriefPanel — displays Granite AI explanation or deterministic fallback.
 *
 * ARCHITECTURE: Both ai_generated=true and ai_generated=false are valid
 * operational states — neither is displayed as an error.
 *
 * ai_generated=true  → green "🤖 IBM Granite" badge + model_id
 * ai_generated=false → gray "⚙️ Deterministic Fallback" badge
 */

import type { AIExplanation } from '@/services/types'
import LoadingSpinner from './LoadingSpinner'
import SeverityBadge from './SeverityBadge'

interface AIBriefPanelProps {
  title: string
  explanation: AIExplanation | null
  loading: boolean
  entityId: string | null
  onRequest: () => void
}

function AIBadge({ aiGenerated, modelId }: { aiGenerated: boolean; modelId: string | null }) {
  if (aiGenerated) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full bg-green-700 px-3 py-1 text-xs font-semibold text-white">
        <span>🤖 IBM Granite</span>
        {modelId && (
          <span className="text-green-200 font-normal text-xs">{modelId}</span>
        )}
      </div>
    )
  }
  return (
    <div className="inline-flex items-center rounded-full bg-gray-600 px-3 py-1 text-xs font-semibold text-gray-200">
      ⚙️ Deterministic Fallback
    </div>
  )
}

export default function AIBriefPanel({
  title,
  explanation,
  loading,
  entityId,
  onRequest,
}: AIBriefPanelProps) {
  if (!entityId) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">
        Select a shipment or disruption and click &ldquo;Get AI Brief&rdquo; to generate an operational summary.
      </p>
    )
  }

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-4 w-32 rounded bg-gray-700" />
        <div className="h-5 w-3/4 rounded bg-gray-700" />
        <div className="h-3 w-full rounded bg-gray-700" />
        <div className="h-3 w-5/6 rounded bg-gray-700" />
        <div className="h-3 w-4/5 rounded bg-gray-700" />
        <LoadingSpinner label="Generating AI brief…" />
      </div>
    )
  }

  if (!explanation) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-400">
          Click below to generate an AI operational brief for <strong className="font-mono text-white">{entityId}</strong>.
        </p>
        <button
          onClick={onRequest}
          className="w-full rounded-lg bg-blue-700 px-4 py-3 text-sm font-semibold text-white
                     hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-400
                     transition-colors"
          aria-label={`Get AI brief for ${entityId}`}
        >
          🤖 {title}
        </button>
      </div>
    )
  }

  const generatedAt = new Date(explanation.generated_at).toLocaleString()

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <AIBadge aiGenerated={explanation.ai_generated} modelId={explanation.model_id} />
        <SeverityBadge severity={explanation.severity} size="md" />
      </div>

      <div className="border-t border-gray-700 pt-3">
        <p className="text-base font-bold text-white leading-snug">
          {explanation.headline}
        </p>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-1">
          Situation Analysis
        </p>
        <p className="text-sm text-gray-300 leading-relaxed">{explanation.explanation}</p>
      </div>

      <div className="rounded-lg border border-blue-700 bg-blue-900/20 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-1">
          Dispatcher Action
        </p>
        <p className="text-sm font-semibold text-white">{explanation.recommended_action}</p>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-600">Generated: {generatedAt}</p>
        <button
          onClick={onRequest}
          className="text-xs text-blue-400 hover:text-blue-300 focus:outline-none focus:underline"
          aria-label="Refresh AI brief"
        >
          ↻ Refresh
        </button>
      </div>
    </div>
  )
}
