import { render, screen } from '@testing-library/react'
import RiskScoreGauge from '@/components/RiskScoreGauge'

describe('RiskScoreGauge', () => {
  test('renders score 82.4 as-is (0–100 engine scale)', () => {
    render(<RiskScoreGauge score={82.4} severity="CRITICAL" />)
    expect(screen.getByText('82.4')).toBeInTheDocument()
  })

  test('renders score 0', () => {
    render(<RiskScoreGauge score={0} severity="LOW" />)
    expect(screen.getByText('0.0')).toBeInTheDocument()
  })

  test('renders score 100', () => {
    render(<RiskScoreGauge score={100} severity="CRITICAL" />)
    expect(screen.getByText('100.0')).toBeInTheDocument()
  })

  test('CRITICAL severity applies red bar class', () => {
    const { container } = render(<RiskScoreGauge score={82.4} severity="CRITICAL" />)
    const bar = container.querySelector('[role="progressbar"]')
    expect(bar).toHaveClass('bg-red-600')
  })

  test('LOW severity applies green bar class', () => {
    const { container } = render(<RiskScoreGauge score={12} severity="LOW" />)
    const bar = container.querySelector('[role="progressbar"]')
    expect(bar).toHaveClass('bg-green-600')
  })

  /**
   * SCALE INVARIANT TEST
   * Verifies RiskScoreGauge does NOT multiply the score by 100 internally.
   * If score=0.824 (the DB current_risk_score) were accidentally passed,
   * it must render as 0.8, not 82.4.
   */
  test('scale invariant: score=0.824 renders as 0.8, not 82.4', () => {
    render(<RiskScoreGauge score={0.824} severity="LOW" />)
    expect(screen.getByText('0.8')).toBeInTheDocument()
    expect(screen.queryByText('82.4')).not.toBeInTheDocument()
  })

  test('progressbar aria-valuenow matches score', () => {
    const { container } = render(<RiskScoreGauge score={55} severity="HIGH" />)
    const bar = container.querySelector('[role="progressbar"]')
    expect(bar).toHaveAttribute('aria-valuenow', '55')
  })
})
