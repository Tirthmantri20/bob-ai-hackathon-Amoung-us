import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DisruptionMonitor from '@/components/DisruptionMonitor'
import { mockDisruption } from './fixtures'

describe('DisruptionMonitor', () => {
  const disruptions = [
    mockDisruption({ id: 'DIS-501', severity: 'HIGH', title: 'Winter Storm Warning' }),
    mockDisruption({ id: 'DIS-502', severity: 'MEDIUM', title: 'Interstate Resurfacing' }),
    mockDisruption({ id: 'DIS-503', severity: 'CRITICAL', title: 'Port Power Outage' }),
  ]

  test('renders correct disruption count', () => {
    render(
      <DisruptionMonitor disruptions={disruptions} selectedId={null} onSelect={jest.fn()} />
    )
    expect(screen.getAllByRole('button')).toHaveLength(3)
  })

  test('each disruption shows its title', () => {
    render(
      <DisruptionMonitor disruptions={disruptions} selectedId={null} onSelect={jest.fn()} />
    )
    expect(screen.getByText('Winter Storm Warning')).toBeInTheDocument()
    expect(screen.getByText('Interstate Resurfacing')).toBeInTheDocument()
    expect(screen.getByText('Port Power Outage')).toBeInTheDocument()
  })

  test('severity badges render for each disruption', () => {
    render(
      <DisruptionMonitor disruptions={disruptions} selectedId={null} onSelect={jest.fn()} />
    )
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
  })

  test('clicking a disruption calls onSelect with correct ID', async () => {
    const onSelect = jest.fn()
    render(
      <DisruptionMonitor disruptions={disruptions} selectedId={null} onSelect={onSelect} />
    )
    await userEvent.click(screen.getByLabelText(/Select disruption DIS-501/i))
    expect(onSelect).toHaveBeenCalledWith('DIS-501')
  })

  test('selected disruption has aria-pressed=true', () => {
    render(
      <DisruptionMonitor disruptions={disruptions} selectedId="DIS-503" onSelect={jest.fn()} />
    )
    expect(screen.getByLabelText(/Select disruption DIS-503/i)).toHaveAttribute('aria-pressed', 'true')
  })

  test('empty disruptions list shows no-disruptions message', () => {
    render(
      <DisruptionMonitor disruptions={[]} selectedId={null} onSelect={jest.fn()} />
    )
    expect(screen.getByText(/No active disruptions/i)).toBeInTheDocument()
  })
})
