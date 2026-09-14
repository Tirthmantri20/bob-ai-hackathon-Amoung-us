'use client'

/**
 * ControlTowerMap — Leaflet operational map.
 *
 * Loaded client-side only via next/dynamic with ssr:false.
 * Uses OpenStreetMap tiles — no API key required.
 *
 * Renders:
 *   - Shipment markers (colored by severity)
 *   - Disruption markers
 *   - Disruption radius circles (from proximity_radius_km)
 *   - Route polylines (from RouteData waypoints)
 *
 * Fleet markers are omitted: seeded fleet assets have no GPS coordinates.
 * No coordinates are invented.
 */

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import React, { useEffect } from 'react'
import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer } from 'react-leaflet'
import type { Disruption, DisruptionImpact, RouteData, Shipment, ShipmentRisk } from '@/services/types'

// Fix default Leaflet marker icons broken by webpack bundling
// Uses official CDN PNGs — no local asset copying required.
if (typeof window !== 'undefined') {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (L.Icon.Default.prototype as any)._getIconUrl
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  })
}

// ---------------------------------------------------------------------------
// Severity → map icon color
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#dc2626',  // red-600
  HIGH:     '#f97316',  // orange-500
  MEDIUM:   '#eab308',  // yellow-500
  LOW:      '#16a34a',  // green-600
  UNKNOWN:  '#6b7280',  // gray-500
}

function shipmentIcon(severity: string): L.DivIcon {
  const color = SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.UNKNOWN
  return L.divIcon({
    className: '',
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 0 4px rgba(0,0,0,0.6);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

function disruptionIcon(severity: string): L.DivIcon {
  const color = SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.UNKNOWN
  return L.divIcon({
    className: '',
    html: `<div style="
      width:0;height:0;
      border-left:9px solid transparent;
      border-right:9px solid transparent;
      border-bottom:16px solid ${color};
      filter:drop-shadow(0 0 3px rgba(0,0,0,0.5));
    "></div>`,
    iconSize: [18, 16],
    iconAnchor: [9, 16],
  })
}

function circleColor(severity: string): string {
  if (severity === 'CRITICAL' || severity === 'HIGH') return '#dc2626'
  if (severity === 'MEDIUM') return '#f97316'
  return '#eab308'
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ControlTowerMapProps {
  shipments: Shipment[]
  activeRisks: Map<string, ShipmentRisk>
  disruptions: Disruption[]
  disruptionImpacts: Map<string, DisruptionImpact>
  routes: RouteData[]
  selectedShipmentId: string | null
  selectedDisruptionId: string | null
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ControlTowerMap({
  shipments,
  activeRisks,
  disruptions,
  disruptionImpacts,
  routes,
}: ControlTowerMapProps) {
  // Suppress "Map already initialized" error in React StrictMode
  useEffect(() => {}, [])

  return (
    <MapContainer
      center={[39.8283, -98.5795]}  // geographic center of USA
      zoom={4}
      style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Shipment markers */}
      {shipments.map((shp) => {
        if (shp.current_lat === null || shp.current_lon === null) return null
        const risk = activeRisks.get(shp.id)
        const severity = risk?.severity ?? 'UNKNOWN'
        return (
          <Marker
            key={shp.id}
            position={[shp.current_lat, shp.current_lon]}
            icon={shipmentIcon(severity)}
          >
            <Popup>
              <div className="text-sm">
                <strong>{shp.id}</strong>
                <br />
                {shp.cargo_type}
                <br />
                📍 {shp.current_location_name ?? 'En Route'}
                <br />
                Severity: <strong>{severity}</strong>
                {risk && (
                  <>
                    <br />
                    Risk: <strong>{risk.total_score.toFixed(1)} / 100</strong>
                  </>
                )}
              </div>
            </Popup>
          </Marker>
        )
      })}

      {/* Disruption markers + radius circles */}
      {disruptions.map((dis) => {
        if (dis.geometry_lat === null || dis.geometry_lon === null) return null
        const impact = disruptionImpacts.get(dis.id)
        const radiusM = impact
          ? impact.proximity_radius_km * 1000
          : 100_000  // fallback 100 km if impact not yet loaded

        return (
          <React.Fragment key={dis.id}>
            <Marker
              position={[dis.geometry_lat, dis.geometry_lon]}
              icon={disruptionIcon(dis.severity)}
            >
              <Popup>
                <div className="text-sm">
                  <strong>{dis.id}</strong>
                  <br />
                  {dis.title}
                  <br />
                  Severity: <strong>{dis.severity}</strong>
                  <br />
                  Radius: <strong>{impact ? `${impact.proximity_radius_km} km` : 'loading…'}</strong>
                </div>
              </Popup>
            </Marker>
            <Circle
              center={[dis.geometry_lat, dis.geometry_lon]}
              radius={radiusM}
              pathOptions={{
                color: circleColor(dis.severity),
                fillColor: circleColor(dis.severity),
                fillOpacity: 0.05,
                weight: 2,
              }}
            />
          </React.Fragment>
        )
      })}

      {/* Route polylines */}
      {routes.map((route) => {
        if (!route.waypoints || route.waypoints.length < 2) return null
        const positions = route.waypoints.map((wp) => [wp.lat, wp.lon] as [number, number])
        return (
          <Polyline
            key={route.route_id}
            positions={positions}
            pathOptions={{ color: '#3b82f6', weight: 2, opacity: 0.6 }}
          />
        )
      })}
    </MapContainer>
  )
}
