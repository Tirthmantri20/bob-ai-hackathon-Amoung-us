/**
 * API client unit tests — mocked fetch, no live network.
 */

import { ApiError, api } from '@/services/api'
import { mockShipment, mockShipmentRisk } from './fixtures'

const mockFetch = jest.fn()
global.fetch = mockFetch

function makeResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('api client', () => {
  test('getShipments calls correct URL and returns data', async () => {
    const ships = [mockShipment()]
    mockFetch.mockResolvedValueOnce(makeResponse(ships))
    const result = await api.getShipments()
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/shipments/'),
      undefined
    )
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('SHP-1002')
  })

  test('getShipmentRisk calls correct URL', async () => {
    const risk = mockShipmentRisk()
    mockFetch.mockResolvedValueOnce(makeResponse(risk))
    const result = await api.getShipmentRisk('SHP-1002')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/shipments/SHP-1002/risk'),
      undefined
    )
    expect(result.total_score).toBe(82.4)
  })

  test('explainShipmentRisk sends correct POST body', async () => {
    const explanation = { use_case: 'shipment_risk', entity_id: 'SHP-1002', ai_generated: true }
    mockFetch.mockResolvedValueOnce(makeResponse(explanation))
    await api.explainShipmentRisk('SHP-1002')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/explain/shipment-risk'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ entity_id: 'SHP-1002', use_case: 'shipment_risk' }),
      })
    )
  })

  test('apiFetch throws ApiError on 404', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ detail: 'Not found' }, 404))
    const err = await api.getShipment('MISSING').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(404)
  })

  test('apiFetch throws ApiError on 500', async () => {
    mockFetch.mockResolvedValueOnce(makeResponse({ detail: 'Internal error' }, 500))
    await expect(api.getDisruptions()).rejects.toThrow(ApiError)
  })

  test('BASE_URL uses env var or defaults to localhost:8000', () => {
    // The module reads process.env.NEXT_PUBLIC_API_URL at import time.
    // Without the var set, the fetch URL contains localhost:8000.
    mockFetch.mockResolvedValueOnce(makeResponse([]))
    api.getShipments()
    const calledUrl = mockFetch.mock.calls[0][0] as string
    expect(calledUrl).toMatch(/localhost:8000|127\.0\.0\.1:8000/)
  })
})
