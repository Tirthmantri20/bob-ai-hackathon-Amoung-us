/**
 * services/api.ts — SupplyGuard AI Typed API Client
 *
 * Single module wrapping all FastAPI endpoints used by the frontend.
 * All components call functions from this module — no component
 * constructs its own fetch URL.
 *
 * Base URL: NEXT_PUBLIC_API_URL (defaults to http://localhost:8000).
 * No secrets are embedded here. The only public variable is the API URL.
 */

import type {
  AIExplanation,
  ColdChainStatus,
  Disruption,
  DisruptionImpact,
  FleetAsset,
  FleetMatch,
  HealthResponse,
  RouteData,
  RouteRecommendation,
  Shipment,
  ShipmentRisk,
} from './types'

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// ---------------------------------------------------------------------------
// Generic fetcher
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, options)
  if (!res.ok) {
    const text = await res.text()
    throw new ApiError(res.status, text)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Typed endpoint functions
// ---------------------------------------------------------------------------

export const api = {
  // ── Health ─────────────────────────────────────────────────────────────
  checkHealth: () =>
    apiFetch<HealthResponse>('/health'),

  // ── Shipments ──────────────────────────────────────────────────────────
  getShipments: () =>
    apiFetch<Shipment[]>('/api/shipments/'),

  getShipment: (id: string) =>
    apiFetch<Shipment>(`/api/shipments/${id}`),

  createShipment: (payload: Record<string, unknown>) =>
    apiFetch<Shipment>('/api/shipments/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  /** Returns total_score 0–100 (engine scale). Use this for the risk gauge. */
  getShipmentRisk: (id: string) =>
    apiFetch<ShipmentRisk>(`/api/shipments/${id}/risk`),

  getShipmentColdChain: (id: string) =>
    apiFetch<ColdChainStatus>(`/api/shipments/${id}/cold-chain`),

  getShipmentRoutes: (id: string) =>
    apiFetch<RouteRecommendation>(`/api/shipments/${id}/routes`),

  getShipmentFleetMatch: (id: string) =>
    apiFetch<FleetMatch>(`/api/shipments/${id}/fleet-match`),

  // ── Risk batch ─────────────────────────────────────────────────────────
  getActiveRisk: () =>
    apiFetch<ShipmentRisk[]>('/api/risk/active'),

  // ── Disruptions ────────────────────────────────────────────────────────
  getDisruptions: () =>
    apiFetch<Disruption[]>('/api/disruptions/'),

  createDisruption: (payload: Record<string, unknown>) =>
    apiFetch<Disruption>('/api/disruptions/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getDisruptionImpact: (id: string) =>
    apiFetch<DisruptionImpact>(`/api/disruptions/${id}/affected-shipments`),

  // ── Fleet ──────────────────────────────────────────────────────────────
  getFleetAssets: () =>
    apiFetch<FleetAsset[]>('/api/fleet/'),

  createFleetAsset: (payload: Record<string, unknown>) =>
    apiFetch<FleetAsset>('/api/fleet/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // ── Routes catalog (map/display data — not optimizer output) ───────────
  getRoutes: () =>
    apiFetch<RouteData[]>('/api/routes/'),

  // ── AI explanations ────────────────────────────────────────────────────
  explainShipmentRisk: (entityId: string) =>
    apiFetch<AIExplanation>('/api/explain/shipment-risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_id: entityId, use_case: 'shipment_risk' }),
    }),

  explainDisruptionImpact: (entityId: string) =>
    apiFetch<AIExplanation>('/api/explain/disruption-impact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_id: entityId, use_case: 'disruption_impact' }),
    }),
}
