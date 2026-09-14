import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ShipmentRoster from '@/components/ShipmentRoster'
import { mockShipment, mockShipmentRisk } from './fixtures'

function makeRiskMap(risks: ReturnType<typeof mockShipmentRisk>[]) {
  return new Map(risks.map((r) => [r.shipment_id, r]))
}

describe('ShipmentRoster', () => {
  const ships = [
    mockShipment({ id: 'SHP-1001', status: 'IN_TRANSIT', current_location_name: 'Indianapolis, IN' }),
    mockShipment({ id: 'SHP-1002', status: 'ALERT_DISRUPTION' }),
    mockShipment({ id: 'SHP-1003', status: 'IN_TRANSIT' }),
  ]

  test('renders correct number of rows', () => {
    render(
      <ShipmentRoster
        shipments={ships}
        activeRisks={new Map()}
        selectedId={null}
        onSelect={jest.fn()}
      />
    )
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
  })

  test('each row shows shipment ID', () => {
    render(
      <ShipmentRoster
        shipments={ships}
        activeRisks={new Map()}
        selectedId={null}
        onSelect={jest.fn()}
      />
    )
    expect(screen.getByText('SHP-1001')).toBeInTheDocument()
    expect(screen.getByText('SHP-1002')).toBeInTheDocument()
    expect(screen.getByText('SHP-1003')).toBeInTheDocument()
  })

  test('severity badge renders from activeRisks map', () => {
    const risks = [mockShipmentRisk({ shipment_id: 'SHP-1002', severity: 'CRITICAL' })]
    render(
      <ShipmentRoster
        shipments={ships}
        activeRisks={makeRiskMap(risks)}
        selectedId={null}
        onSelect={jest.fn()}
      />
    )
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
  })

  test('UNKNOWN severity shown for shipments with no risk data', () => {
    render(
      <ShipmentRoster
        shipments={[mockShipment({ id: 'SHP-9999' })]}
        activeRisks={new Map()}
        selectedId={null}
        onSelect={jest.fn()}
      />
    )
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
  })

  test('clicking a row calls onSelect with the correct ID', async () => {
    const onSelect = jest.fn()
    render(
      <ShipmentRoster
        shipments={ships}
        activeRisks={new Map()}
        selectedId={null}
        onSelect={onSelect}
      />
    )
    await userEvent.click(screen.getByLabelText(/Select shipment SHP-1002/i))
    expect(onSelect).toHaveBeenCalledWith('SHP-1002')
  })

  test('selected row has aria-pressed=true', () => {
    render(
      <ShipmentRoster
        shipments={ships}
        activeRisks={new Map()}
        selectedId="SHP-1001"
        onSelect={jest.fn()}
      />
    )
    expect(screen.getByLabelText(/Select shipment SHP-1001/i)).toHaveAttribute('aria-pressed', 'true')
  })
})
