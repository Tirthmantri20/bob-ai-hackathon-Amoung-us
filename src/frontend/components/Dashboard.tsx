'use client'

/**
 * Dashboard — top-level orchestrator.
 *
 * All state lives here. Child components receive data as props.
 * Independent AI states for shipment and disruption (decision 18).
 * SHP-1002 is pre-selected on initial load (decision 11).
 */

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useState } from 'react'

import { ApiError, api } from '@/services/api'
import type {
  AIExplanation,
  ColdChainStatus,
  Disruption,
  DisruptionImpact,
  FleetAsset,
  FleetMatch,
  RouteData,
  RouteRecommendation,
  Shipment,
  ShipmentRisk,
} from '@/services/types'

import AIBriefPanel from './AIBriefPanel'
import DisruptionImpactPanel from './DisruptionImpactPanel'
import DisruptionMonitor from './DisruptionMonitor'
import ErrorBanner from './ErrorBanner'
import Header from './Header'
import LoadingSpinner from './LoadingSpinner'
import ShipmentDetailPanel from './ShipmentDetailPanel'
import ShipmentRoster from './ShipmentRoster'

// Leaflet map loaded client-side only (no SSR)
const ControlTowerMap = dynamic(
  () => import('../maps/ControlTowerMap'),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-gray-500 text-sm">
        Loading map…
      </div>
    ),
  }
)

const INITIAL_SHIPMENT_ID = 'SHP-1002'

export default function Dashboard() {
  // ── Mount data ────────────────────────────────────────────────────────────
  const [shipments, setShipments] = useState<Shipment[]>([])
  const [activeRisks, setActiveRisks] = useState<Map<string, ShipmentRisk>>(new Map())
  const [disruptions, setDisruptions] = useState<Disruption[]>([])
  const [_fleetAssets, setFleetAssets] = useState<FleetAsset[]>([])
  const [routes, setRoutes] = useState<RouteData[]>([])
  const [mountLoading, setMountLoading] = useState(true)
  const [mountError, setMountError] = useState<string | null>(null)
  const [backendHealthy, setBackendHealthy] = useState(true)

  // ── Selection state ───────────────────────────────────────────────────────
  const [selectedShipmentId, setSelectedShipmentId] = useState<string | null>(INITIAL_SHIPMENT_ID)
  const [selectedDisruptionId, setSelectedDisruptionId] = useState<string | null>(null)

  // ── Shipment detail ───────────────────────────────────────────────────────
  const [shipmentRisk, setShipmentRisk] = useState<ShipmentRisk | null>(null)
  const [coldChain, setColdChain] = useState<ColdChainStatus | null>(null)
  const [routeRec, setRouteRec] = useState<RouteRecommendation | null>(null)
  const [fleetMatch, setFleetMatch] = useState<FleetMatch | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // ── Disruption impact ─────────────────────────────────────────────────────
  const [disruptionImpacts, setDisruptionImpacts] = useState<Map<string, DisruptionImpact>>(new Map())
  const [currentImpact, setCurrentImpact] = useState<DisruptionImpact | null>(null)
  const [impactLoading, setImpactLoading] = useState(false)

  // ── AI state — INDEPENDENT for shipment and disruption (decision 18) ──────
  const [shipmentAiExplanation, setShipmentAiExplanation] = useState<AIExplanation | null>(null)
  const [shipmentAiLoading, setShipmentAiLoading] = useState(false)
  const [disruptionAiExplanation, setDisruptionAiExplanation] = useState<AIExplanation | null>(null)
  const [disruptionAiLoading, setDisruptionAiLoading] = useState(false)
  const [watsonxLive, setWatsonxLive] = useState<boolean | null>(null)

  // ── Fetch shipment detail ─────────────────────────────────────────────────
  const fetchShipmentDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    setShipmentRisk(null)
    setColdChain(null)
    setRouteRec(null)
    setFleetMatch(null)
    setShipmentAiExplanation(null)
    try {
      const [risk, cc, routes, fleet] = await Promise.all([
        api.getShipmentRisk(id),
        api.getShipmentColdChain(id),
        api.getShipmentRoutes(id),
        api.getShipmentFleetMatch(id),
      ])
      setShipmentRisk(risk)
      setColdChain(cc)
      setRouteRec(routes)
      setFleetMatch(fleet)
    } catch (err) {
      console.error('Shipment detail fetch failed:', err)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  // ── Fetch disruption impact ───────────────────────────────────────────────
  const fetchDisruptionImpact = useCallback(async (id: string) => {
    setImpactLoading(true)
    setCurrentImpact(null)
    setDisruptionAiExplanation(null)
    try {
      const impact = await api.getDisruptionImpact(id)
      setCurrentImpact(impact)
      setDisruptionImpacts((prev) => new Map(prev).set(id, impact))
    } catch (err) {
      console.error('Disruption impact fetch failed:', err)
    } finally {
      setImpactLoading(false)
    }
  }, [])

  // ── Mount effect ──────────────────────────────────────────────────────────
  useEffect(() => {
    async function loadAll() {
      setMountLoading(true)

      // Health check
      try {
        await api.checkHealth()
        setBackendHealthy(true)
      } catch {
        setBackendHealthy(false)
        setMountError('Backend unavailable — start FastAPI on port 8000.')
        setMountLoading(false)
        return
      }

      // Parallel load of all list data
      try {
        const [ships, risks, disrs, fleet, rts] = await Promise.all([
          api.getShipments(),
          api.getActiveRisk(),
          api.getDisruptions(),
          api.getFleetAssets(),
          api.getRoutes(),
        ])
        setShipments(ships)
        const riskMap = new Map(risks.map((r) => [r.shipment_id, r]))
        setActiveRisks(riskMap)
        setDisruptions(disrs)
        setFleetAssets(fleet)
        setRoutes(rts)
      } catch (err) {
        const msg = err instanceof ApiError ? `API Error ${err.status}` : 'Failed to load data'
        setMountError(msg)
      } finally {
        setMountLoading(false)
      }
    }
    loadAll()
  }, [])

  // ── Pre-select SHP-1002 after shipments load ──────────────────────────────
  useEffect(() => {
    if (shipments.length > 0 && selectedShipmentId === INITIAL_SHIPMENT_ID) {
      fetchShipmentDetail(INITIAL_SHIPMENT_ID)
    }
    // Only run when shipments first arrive
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shipments])

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleSelectShipment = useCallback((id: string) => {
    setSelectedShipmentId(id)
    fetchShipmentDetail(id)
  }, [fetchShipmentDetail])

  const handleSelectDisruption = useCallback((id: string) => {
    setSelectedDisruptionId(id)
    fetchDisruptionImpact(id)
  }, [fetchDisruptionImpact])

  const handleShipmentAIBrief = useCallback(async () => {
    if (!selectedShipmentId) return
    setShipmentAiLoading(true)
    setShipmentAiExplanation(null)
    try {
      const result = await api.explainShipmentRisk(selectedShipmentId)
      setShipmentAiExplanation(result)
      setWatsonxLive(result.ai_generated)
    } catch (err) {
      console.error('AI brief failed:', err)
    } finally {
      setShipmentAiLoading(false)
    }
  }, [selectedShipmentId])

  const handleDisruptionAIBrief = useCallback(async () => {
    if (!selectedDisruptionId) return
    setDisruptionAiLoading(true)
    setDisruptionAiExplanation(null)
    try {
      const result = await api.explainDisruptionImpact(selectedDisruptionId)
      setDisruptionAiExplanation(result)
      setWatsonxLive(result.ai_generated)
    } catch (err) {
      console.error('Disruption AI brief failed:', err)
    } finally {
      setDisruptionAiLoading(false)
    }
  }, [selectedDisruptionId])

  const selectedShipment = shipments.find((s) => s.id === selectedShipmentId) ?? null
  const selectedDisruption = disruptions.find((d) => d.id === selectedDisruptionId) ?? null

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen flex-col bg-slate-100 text-slate-900">
      <Header backendHealthy={backendHealthy} watsonxLive={watsonxLive} />

      <main className="flex-1 p-4 md:p-6 space-y-4 max-w-7xl mx-auto w-full">
        {mountError && (
          <ErrorBanner
            message={mountError}
            onRetry={() => window.location.reload()}
          />
        )}

        {mountLoading && !mountError && (
          <LoadingSpinner label="Loading SupplyGuard data…" />
        )}

        {!mountLoading && !mountError && (
          <>
            {/* ── KPI Summary Cards ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Shipments</span>
                  <span className="text-base">📦</span>
                </div>
                <p className="mt-1 text-2xl font-black text-slate-900 tabular-nums">{shipments.length}</p>
                <p className="text-[11px] text-slate-500 font-medium">Real-time GPS tracked</p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">High Risk Alerts</span>
                  <span className="text-base">🚨</span>
                </div>
                <p className="mt-1 text-2xl font-black text-red-600 tabular-nums">
                  {Array.from(activeRisks.values()).filter((r) => r.severity === 'CRITICAL' || r.severity === 'HIGH').length}
                </p>
                <p className="text-[11px] text-slate-500 font-medium">Requiring immediate action</p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Disruptions</span>
                  <span className="text-base">⚠️</span>
                </div>
                <p className="mt-1 text-2xl font-black text-amber-600 tabular-nums">{disruptions.length}</p>
                <p className="text-[11px] text-slate-500 font-medium">Weather &amp; corridor halts</p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Monitored Routes</span>
                  <span className="text-base">🛣️</span>
                </div>
                <p className="mt-1 text-2xl font-black text-blue-600 tabular-nums">{routes.length}</p>
                <p className="text-[11px] text-slate-500 font-medium">Optimized bypass corridors</p>
              </div>
            </div>

            {/* ── Upper grid: roster + disruptions + map ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left col: shipment roster & disruptions */}
              <div className="lg:col-span-1 space-y-4">
                <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                    Active Shipments ({shipments.length})
                  </h2>
                  <ShipmentRoster
                    shipments={shipments}
                    activeRisks={activeRisks}
                    selectedId={selectedShipmentId}
                    onSelect={handleSelectShipment}
                  />
                </section>

                <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                    Disruption Monitor ({disruptions.length})
                  </h2>
                  <DisruptionMonitor
                    disruptions={disruptions}
                    selectedId={selectedDisruptionId}
                    onSelect={handleSelectDisruption}
                  />
                </section>
              </div>

              {/* Right col: map */}
              <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm overflow-hidden flex flex-col" style={{ minHeight: '400px' }}>
                <div className="px-2 py-1.5 border-b border-slate-100 flex items-center justify-between">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Geospatial Fleet &amp; Disruption Map
                  </h2>
                  <span className="text-[11px] text-slate-400">Click pins for live telematics</span>
                </div>
                <div className="flex-1 w-full rounded-lg overflow-hidden relative min-h-[350px]">
                  <ControlTowerMap
                    shipments={shipments}
                    activeRisks={activeRisks}
                    disruptions={disruptions}
                    disruptionImpacts={disruptionImpacts}
                    routes={routes}
                    selectedShipmentId={selectedShipmentId}
                    selectedDisruptionId={selectedDisruptionId}
                  />
                </div>
              </div>
            </div>

            {/* ── Shipment detail ── */}
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-500">
                Shipment Detail
              </h2>
              <ShipmentDetailPanel
                shipment={selectedShipment}
                risk={shipmentRisk}
                coldChain={coldChain}
                routes={routeRec}
                fleetMatch={fleetMatch}
                loading={detailLoading}
                onRequestAIBrief={handleShipmentAIBrief}
              />
            </section>

            {/* ── Disruption impact ── */}
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-500">
                Disruption Impact
              </h2>
              <DisruptionImpactPanel
                disruption={selectedDisruption}
                impact={currentImpact}
                loading={impactLoading}
                onRequestAIBrief={handleDisruptionAIBrief}
              />
            </section>

            {/* ── AI brief panels (independent) ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                  AI Operational Brief — Shipment
                </h2>
                <AIBriefPanel
                  title={`Get AI Brief for ${selectedShipmentId ?? '—'}`}
                  explanation={shipmentAiExplanation}
                  loading={shipmentAiLoading}
                  entityId={selectedShipmentId}
                  onRequest={handleShipmentAIBrief}
                />
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                  AI Operational Brief — Disruption
                </h2>
                <AIBriefPanel
                  title={`Get AI Brief for ${selectedDisruptionId ?? '—'}`}
                  explanation={disruptionAiExplanation}
                  loading={disruptionAiLoading}
                  entityId={selectedDisruptionId}
                  onRequest={handleDisruptionAIBrief}
                />
              </section>
            </div>
          </>
        )}
      </main>

      <footer className="border-t border-slate-200 bg-white px-6 py-3.5 text-center text-xs text-slate-500 font-medium shadow-xs">
        SupplyGuard AI &bull; Autonomous Supply Chain Intelligence powered by IBM watsonx.ai &amp; Granite
      </footer>
    </div>
  )
}
