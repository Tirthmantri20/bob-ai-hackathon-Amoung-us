import { render, screen } from '@testing-library/react'
import ColdChainPanel from '@/components/ColdChainPanel'
import { mockColdChain } from './fixtures'

describe('ColdChainPanel', () => {
  test('is_in_excursion=true renders EXCURSION ACTIVE', () => {
    render(<ColdChainPanel data={mockColdChain({ is_in_excursion: true })} loading={false} />)
    expect(screen.getByText(/EXCURSION ACTIVE/i)).toBeInTheDocument()
  })

  test('is_in_excursion=false renders Within Specification', () => {
    render(
      <ColdChainPanel
        data={mockColdChain({ is_in_excursion: false, deviation_c: 0, severity: 'OK' })}
        loading={false}
      />
    )
    expect(screen.getByText(/Within Specification/i)).toBeInTheDocument()
  })

  test('is_destructive=true renders destructive warning', () => {
    render(
      <ColdChainPanel
        data={mockColdChain({ is_destructive: true, is_in_excursion: true })}
        loading={false}
      />
    )
    expect(screen.getByText(/Destructive Threshold/i)).toBeInTheDocument()
  })

  test('positive deviation renders with + sign', () => {
    render(<ColdChainPanel data={mockColdChain({ deviation_c: 2.8 })} loading={false} />)
    expect(screen.getByText('+2.8°C')).toBeInTheDocument()
  })

  test('negative deviation renders with - sign', () => {
    render(<ColdChainPanel data={mockColdChain({ deviation_c: -1.4 })} loading={false} />)
    expect(screen.getByText('-1.4°C')).toBeInTheDocument()
  })

  test('cargo_rule_found=false renders no-rule message', () => {
    render(
      <ColdChainPanel
        data={mockColdChain({ cargo_rule_found: false })}
        loading={false}
      />
    )
    expect(screen.getByText(/No cargo rule configured/i)).toBeInTheDocument()
  })

  test('compliance standard renders', () => {
    render(
      <ColdChainPanel
        data={mockColdChain({ compliance_standard: 'FDA HACCP Seafood Guidelines' })}
        loading={false}
      />
    )
    expect(screen.getByText(/FDA HACCP/i)).toBeInTheDocument()
  })

  test('loading state shows spinner', () => {
    render(<ColdChainPanel data={null} loading={true} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
