/**
 * ControlTowerMap tests — Leaflet mocked to avoid JSDOM/canvas incompatibility.
 * Focused test: verifies the component renders and passes correct data to markers.
 */

import { render, screen } from '@testing-library/react'
import { mockDisruption, mockDisruptionImpact, mockShipment, mockShipmentRisk } from './fixtures'

// Mock react-leaflet — Leaflet requires browser APIs not available in JSDOM
jest.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children, position }: { children: React.ReactNode; position: [number, number] }) => (
    <div data-testid="marker" data-position={position.join(',')}>{children}</div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popup">{children}</div>
  ),
  Circle: ({ center, radius }: { center: [number, number]; radius: number }) => (
    <div data-testid="circle" data-center={center.join(',')} data-radius={radius} />
  ),
  Polyline: ({ positions }: { positions: [number, number][] }) => (
    <div data-testid="polyline" data-points={positions.length} />
  ),
}))

// Mock leaflet itself
jest.mock('leaflet', () => ({
  divIcon: () => ({}),
  Icon: { Default: { prototype: {}, mergeOptions: jest.fn() } },
}))

import ControlTowerMap from '@/maps/ControlTowerMap'

const baseProps = {
  shipments: [],
  activeRisks: new Map(),
  disruptions: [],
  disruptionImpacts: new Map(),
  routes: [],
  selectedShipmentId: null,
  selectedDisruptionId: null,
}

describe('ControlTowerMap', () => {
  test('renders map container', () => {
    render(<ControlTowerMap {...baseProps} />)
    expect(screen.getByTestId('map-container')).toBeInTheDocument()
  })

  test('renders tile layer', () => {
    render(<ControlTowerMap {...baseProps} />)
    expect(screen.getByTestId('tile-layer')).toBeInTheDocument()
  })

  test('renders shipment markers at correct positions', () => {
    const shp = mockShipment({ current_lat: 45.5152, current_lon: -122.6784 })
    const risk = mockShipmentRisk({ shipment_id: shp.id })
    render(
      <ControlTowerMap
        {...baseProps}
        shipments={[shp]}
        activeRisks={new Map([[shp.id, risk]])}
      />
    )
    const markers = screen.getAllByTestId('marker')
    expect(markers.length).toBeGreaterThanOrEqual(1)
    // Shipment marker at Portland, OR
    const shipMarker = markers.find((m) =>
      m.getAttribute('data-position')?.includes('45.5152')
    )
    expect(shipMarker).toBeDefined()
  })

  test('renders disruption markers for disruptions with geometry', () => {
    const dis = mockDisruption({ geometry_lat: 47.4243, geometry_lon: -121.4138 })
    render(
      <ControlTowerMap
        {...baseProps}
        disruptions={[dis]}
      />
    )
    const markers = screen.getAllByTestId('marker')
    const disMarker = markers.find((m) =>
      m.getAttribute('data-position')?.includes('47.4243')
    )
    expect(disMarker).toBeDefined()
  })

  test('renders disruption radius circles', () => {
    const dis = mockDisruption({ geometry_lat: 47.4243, geometry_lon: -121.4138 })
    const impact = mockDisruptionImpact()
    render(
      <ControlTowerMap
        {...baseProps}
        disruptions={[dis]}
        disruptionImpacts={new Map([[dis.id, impact]])}
      />
    )
    const circles = screen.getAllByTestId('circle')
    expect(circles.length).toBeGreaterThanOrEqual(1)
    // Radius should be proximity_radius_km * 1000 = 200 * 1000 = 200000 meters
    const circle = circles[0]
    expect(circle.getAttribute('data-radius')).toBe('200000')
  })

  test('skips shipments without GPS coordinates', () => {
    const shp = mockShipment({ current_lat: null, current_lon: null })
    render(<ControlTowerMap {...baseProps} shipments={[shp]} />)
    // No markers should be rendered for null coordinates
    expect(screen.queryAllByTestId('marker')).toHaveLength(0)
  })
})
