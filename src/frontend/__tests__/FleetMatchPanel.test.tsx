import { render, screen } from '@testing-library/react'
import FleetMatchPanel from '@/components/FleetMatchPanel'
import { mockFleetMatch } from './fixtures'

describe('FleetMatchPanel', () => {
  test('no_asset_found=true renders informational message (not an error)', () => {
    render(<FleetMatchPanel data={mockFleetMatch(true)} loading={false} />)
    expect(screen.getByText(/No Alternative Assets Available/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  test('recommended asset shows Top Match badge', () => {
    render(<FleetMatchPanel data={mockFleetMatch()} loading={false} />)
    expect(screen.getByText('⭐ Top Match')).toBeInTheDocument()
  })

  test('asset ID renders', () => {
    render(<FleetMatchPanel data={mockFleetMatch()} loading={false} />)
    expect(screen.getByText('FLT-302')).toBeInTheDocument()
  })

  test('cooling capability renders', () => {
    render(<FleetMatchPanel data={mockFleetMatch()} loading={false} />)
    expect(screen.getByText(/Standard Cold/i)).toBeInTheDocument()
  })

  test('proximity_km renders', () => {
    render(<FleetMatchPanel data={mockFleetMatch()} loading={false} />)
    expect(screen.getByText(/245 km/i)).toBeInTheDocument()
  })

  test('proximity_km=null renders N/A', () => {
    const data = mockFleetMatch()
    data.scored_assets[0].proximity_km = null
    render(<FleetMatchPanel data={data} loading={false} />)
    expect(screen.getByText(/N\/A/i)).toBeInTheDocument()
  })

  test('total_score renders as percentage', () => {
    render(<FleetMatchPanel data={mockFleetMatch()} loading={false} />)
    expect(screen.getByText('83.0%')).toBeInTheDocument()
  })

  test('loading state shows spinner', () => {
    render(<FleetMatchPanel data={null} loading={true} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
