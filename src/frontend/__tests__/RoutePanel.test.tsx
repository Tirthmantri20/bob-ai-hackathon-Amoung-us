import { render, screen } from '@testing-library/react'
import RoutePanel from '@/components/RoutePanel'
import { mockRouteRecommendation } from './fixtures'

describe('RoutePanel', () => {
  test('no_route_found=true renders informational empty state (not an error)', () => {
    render(<RoutePanel data={mockRouteRecommendation(true)} loading={false} />)
    expect(screen.getByText(/No Route Match Found/i)).toBeInTheDocument()
    // Must not show as a backend error — no role="alert"
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  test('no_route_found message explains the corridor mismatch', () => {
    render(<RoutePanel data={mockRouteRecommendation(true)} loading={false} />)
    expect(screen.getByText(/exact origin\/destination match/i)).toBeInTheDocument()
  })

  test('recommended route shows Recommended badge', () => {
    render(<RoutePanel data={mockRouteRecommendation()} loading={false} />)
    expect(screen.getByText('⭐ Recommended')).toBeInTheDocument()
  })

  test('route name renders', () => {
    render(<RoutePanel data={mockRouteRecommendation()} loading={false} />)
    expect(screen.getByText(/Seattle to Denver/i)).toBeInTheDocument()
  })

  test('eta_hours renders', () => {
    render(<RoutePanel data={mockRouteRecommendation()} loading={false} />)
    expect(screen.getByText(/24\.5 hr/i)).toBeInTheDocument()
  })

  test('warnings render as individual items', () => {
    render(<RoutePanel data={mockRouteRecommendation()} loading={false} />)
    expect(screen.getByText(/ICY_BLOCKED/i)).toBeInTheDocument()
  })

  test('score renders as percentage', () => {
    render(<RoutePanel data={mockRouteRecommendation()} loading={false} />)
    expect(screen.getByText('71.0%')).toBeInTheDocument()
  })

  test('loading state shows spinner', () => {
    render(<RoutePanel data={null} loading={true} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
