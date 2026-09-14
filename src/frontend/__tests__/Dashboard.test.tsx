/**
 * Dashboard integration tests — mocked API module, no live network.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  mockAIExplanation,
  mockColdChain,
  mockDisruption,
  mockFleetMatch,
  mockRouteRecommendation,
  mockShipment,
  mockShipmentRisk,
} from './fixtures'

// Mock the entire api module
jest.mock('@/services/api', () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) { super(message) }
  },
  api: {
    checkHealth: jest.fn().mockResolvedValue({ status: 'healthy', timestamp: '2026-09-13T22:00:00Z' }),
    getShipments: jest.fn().mockResolvedValue([
      { id: 'SHP-1001', tracking_number: null, origin: 'Chicago, IL', destination: 'Atlanta, GA',
        cargo_type: 'Pharmaceuticals', cargo_category: 'Cold Chain Grade A',
        required_temp_min_c: 2, required_temp_max_c: 8, status: 'IN_TRANSIT',
        assigned_vehicle_id: 'FLT-302', carrier_id: 'CRR-401',
        estimated_departure: null, estimated_arrival: null,
        current_risk_score: 0.22, current_lat: 39.78, current_lon: -86.14,
        current_location_name: 'Indianapolis, IN' },
      { ...mockShipment(), current_risk_score: 0.78 },
    ]),
    getActiveRisk: jest.fn().mockResolvedValue([
      mockShipmentRisk({ shipment_id: 'SHP-1001', severity: 'LOW', total_score: 22 }),
      mockShipmentRisk({ shipment_id: 'SHP-1002', severity: 'CRITICAL', total_score: 82.4 }),
    ]),
    getDisruptions: jest.fn().mockResolvedValue([mockDisruption()]),
    getFleetAssets: jest.fn().mockResolvedValue([]),
    getRoutes: jest.fn().mockResolvedValue([]),
    getShipmentRisk: jest.fn().mockResolvedValue(mockShipmentRisk()),
    getShipmentColdChain: jest.fn().mockResolvedValue(mockColdChain()),
    getShipmentRoutes: jest.fn().mockResolvedValue(mockRouteRecommendation(true)),
    getShipmentFleetMatch: jest.fn().mockResolvedValue(mockFleetMatch()),
    getDisruptionImpact: jest.fn().mockResolvedValue({
      disruption_id: 'DIS-501',
      disruption_type: 'SEVERE_WEATHER',
      disruption_severity: 'HIGH',
      proximity_radius_km: 200,
      affected_shipments: [],
      assessed_at: '2026-09-13T22:00:00Z',
    }),
    explainShipmentRisk: jest.fn().mockResolvedValue(mockAIExplanation(true)),
    explainDisruptionImpact: jest.fn().mockResolvedValue(mockAIExplanation(false)),
  },
}))

// Mock next/dynamic (Leaflet map)
jest.mock('next/dynamic', () => (fn: () => Promise<unknown>) => {
  const Comp = () => <div data-testid="mocked-map">Map</div>
  Comp.displayName = 'DynamicMap'
  return Comp
})

import Dashboard from '@/components/Dashboard'

describe('Dashboard integration', () => {
  test('renders the dashboard and loads shipments', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      // Use getAllByText since SHP-1002 appears in multiple places when pre-selected
      expect(screen.getAllByText('SHP-1001').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('SHP-1002').length).toBeGreaterThanOrEqual(1)
    })
  })

  test('SHP-1002 is pre-selected: detail data loads on mount', async () => {
    const { api } = require('@/services/api')
    render(<Dashboard />)
    await waitFor(() => {
      expect(api.getShipmentRisk).toHaveBeenCalledWith('SHP-1002')
      expect(api.getShipmentColdChain).toHaveBeenCalledWith('SHP-1002')
    })
  })

  test('Get AI Brief button calls explainShipmentRisk with correct ID', async () => {
    const { api } = require('@/services/api')
    render(<Dashboard />)
    // Wait for shipment roster to appear
    await waitFor(() => screen.getAllByText('SHP-1002'))
    // Two AI brief buttons exist (ShipmentDetailPanel + AIBriefPanel) — click the first
    const aiButtons = await screen.findAllByRole('button', { name: /Get AI Brief for SHP-1002/i })
    await userEvent.click(aiButtons[0])
    await waitFor(() => {
      expect(api.explainShipmentRisk).toHaveBeenCalledWith('SHP-1002')
    })
  })

  test('ai_generated=false renders Deterministic Fallback badge (not an error)', async () => {
    const { api } = require('@/services/api')
    api.explainShipmentRisk.mockResolvedValueOnce(mockAIExplanation(false))
    render(<Dashboard />)
    await waitFor(() => screen.getAllByText('SHP-1002'))
    const aiButtons = await screen.findAllByRole('button', { name: /Get AI Brief for SHP-1002/i })
    await userEvent.click(aiButtons[0])
    await waitFor(() => {
      expect(screen.getByText(/Deterministic Fallback/i)).toBeInTheDocument()
    })
    // Must not show as an error
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  test('backend unavailable renders ErrorBanner', async () => {
    const { api } = require('@/services/api')
    api.checkHealth.mockRejectedValueOnce(new Error('Connection refused'))
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })
})
