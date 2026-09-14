/**
 * __tests__/fixtures.ts — typed test data matching real Pydantic shapes.
 * All fields match the actual backend schemas exactly.
 */

import type {
  AIExplanation,
  ColdChainStatus,
  Disruption,
  DisruptionImpact,
  FleetMatch,
  RouteRecommendation,
  Shipment,
  ShipmentRisk,
} from '@/services/types'

export function mockShipment(overrides: Partial<Shipment> = {}): Shipment {
  return {
    id: 'SHP-1002',
    tracking_number: 'TRK-2026-9022',
    origin: 'Seattle Port Terminals, WA',
    destination: 'Denver Cold Storage Facility, CO',
    cargo_type: 'Fresh Seafood',
    cargo_category: 'Perishable Frozen',
    required_temp_min_c: -22.0,
    required_temp_max_c: -18.0,
    status: 'ALERT_DISRUPTION',
    assigned_vehicle_id: 'FLT-109',
    carrier_id: 'CRR-403',
    estimated_departure: '2026-09-12T16:00:00Z',
    estimated_arrival: '2026-09-15T10:00:00Z',
    current_risk_score: 0.78,  // 0–1 DB field — never used for risk gauge
    current_lat: 45.5152,
    current_lon: -122.6784,
    current_location_name: 'Portland, OR',
    ...overrides,
  }
}

export function mockShipmentRisk(overrides: Partial<ShipmentRisk> = {}): ShipmentRisk {
  return {
    shipment_id: 'SHP-1002',
    total_score: 82.4,  // 0–100 engine scale
    severity: 'CRITICAL',
    r_disruption: 0.92,
    r_weather: 0.74,
    r_route: 0.65,
    r_cold_chain: 0.88,
    r_business: 0.70,
    contributing_disruption_ids: ['DIS-501'],
    weather_fallback: false,
    cold_chain_fallback: false,
    route_fallback: false,
    assessed_at: '2026-09-13T22:00:00Z',
    ...overrides,
  }
}

export function mockColdChain(overrides: Partial<ColdChainStatus> = {}): ColdChainStatus {
  return {
    shipment_id: 'SHP-1002',
    telemetry_id: 'TEL-FLT-109',
    cargo_rule_found: true,
    is_in_excursion: true,
    is_destructive: false,
    cargo_temp_c: -17.2,
    allowed_min_c: -22.0,
    allowed_max_c: -18.0,
    max_allowable_excursion_temp_c: -15.0,
    deviation_c: 2.8,
    severity: 'WARNING',
    excursion_duration_minutes: null,
    compliance_standard: 'FDA HACCP Seafood Guidelines',
    cargo_category: 'Perishable Frozen',
    grade: 'Perishable Frozen',
    assessed_at: '2026-09-13T22:00:00Z',
    ...overrides,
  }
}

export function mockRouteRecommendation(noRoute = false): RouteRecommendation {
  if (noRoute) {
    return {
      shipment_id: 'SHP-1002',
      scored_routes: [],
      no_route_found: true,
      assessed_at: '2026-09-13T22:00:00Z',
    }
  }
  return {
    shipment_id: 'SHP-1002',
    scored_routes: [
      {
        route_id: 'RT-SEA-DEN-01',
        route_name: 'Seattle to Denver Trans-Mountain Corridor',
        total_score: 0.71,
        eta_hours: 24.5,
        eta_factor: 0.6,
        cost_factor: 0.7,
        disruption_factor: 0.85,
        weather_factor: 0.9,
        cold_chain_factor: 0.3,
        recommended: true,
        warnings: ['Weather station reports ICY_BLOCKED road condition.'],
      },
    ],
    no_route_found: false,
    assessed_at: '2026-09-13T22:00:00Z',
  }
}

export function mockFleetMatch(noAsset = false): FleetMatch {
  if (noAsset) {
    return {
      shipment_id: 'SHP-1002',
      scored_assets: [],
      no_asset_found: true,
      assessed_at: '2026-09-13T22:00:00Z',
    }
  }
  return {
    shipment_id: 'SHP-1002',
    scored_assets: [
      {
        asset_id: 'FLT-302',
        vehicle_type: 'Reefer Truck (53ft)',
        cooling_capability: 'STANDARD_COLD',
        total_score: 0.83,
        proximity_km: 245.0,
        proximity_score: 0.9,
        cargo_compat_score: 0.8,
        refrigeration_score: 1.0,
        capacity_score: 1.0,
        availability_score: 0.7,
        estimated_shipment_weight_kg: 15000,
        asset_capacity_kg: 20000,
        recommended: true,
      },
    ],
    no_asset_found: false,
    assessed_at: '2026-09-13T22:00:00Z',
  }
}

export function mockDisruption(overrides: Partial<Disruption> = {}): Disruption {
  return {
    id: 'DIS-501',
    type: 'SEVERE_WEATHER',
    severity: 'HIGH',
    title: 'Winter Storm Warning - Snoqualmie Pass Closure',
    affected_corridor: 'I-90 Eastbound',
    start_time: '2026-09-12T14:00:00Z',
    expected_end_time: '2026-09-14T06:00:00Z',
    impact_delay_hours: 16.5,
    recommended_reroute: 'I-84 East via Portland',
    geometry_lat: 47.4243,
    geometry_lon: -121.4138,
    ...overrides,
  }
}

export function mockDisruptionImpact(): DisruptionImpact {
  return {
    disruption_id: 'DIS-501',
    disruption_type: 'SEVERE_WEATHER',
    disruption_severity: 'HIGH',
    proximity_radius_km: 200,
    affected_shipments: [
      { shipment_id: 'SHP-1002', shipment_status: 'ALERT_DISRUPTION', distance_km: 142.5 },
    ],
    assessed_at: '2026-09-13T22:00:00Z',
  }
}

export function mockAIExplanation(aiGenerated: boolean): AIExplanation {
  return {
    use_case: 'shipment_risk',
    entity_id: 'SHP-1002',
    headline: 'SHP-1002 CRITICAL: Cold-chain excursion during active DIS-501 storm zone.',
    explanation: 'The shipment is operating in ALERT_DISRUPTION status near the Snoqualmie Pass closure. Cold-chain temperature has deviated +2.8°C above the maximum threshold, indicating an active excursion risk.',
    recommended_action: 'Immediately initiate emergency carrier transfer and pre-position a cold-depot hold.',
    severity: 'CRITICAL',
    ai_generated: aiGenerated,
    model_id: aiGenerated ? 'ibm/granite-3-8b-instruct' : null,
    generated_at: '2026-09-13T22:05:00Z',
  }
}
