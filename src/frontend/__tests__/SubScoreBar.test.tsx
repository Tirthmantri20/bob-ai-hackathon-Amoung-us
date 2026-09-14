import { render, screen } from '@testing-library/react'
import SubScoreBar from '@/components/SubScoreBar'

describe('SubScoreBar', () => {
  test('value 0.92 renders bar width 92%', () => {
    const { container } = render(<SubScoreBar label="Disruption" value={0.92} />)
    const bar = container.querySelector('[role="progressbar"]')
    expect(bar).toHaveStyle({ width: '92%' })
  })

  test('value 0.0 renders zero-width bar', () => {
    const { container } = render(<SubScoreBar label="Weather" value={0} />)
    const bar = container.querySelector('[role="progressbar"]')
    expect(bar).toHaveStyle({ width: '0%' })
  })

  test('label renders', () => {
    render(<SubScoreBar label="Cold Chain" value={0.5} />)
    expect(screen.getByText('Cold Chain')).toBeInTheDocument()
  })

  test('percentage text renders', () => {
    render(<SubScoreBar label="Route" value={0.75} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  test('fallback=true shows estimation annotation', () => {
    render(<SubScoreBar label="Route" value={0.3} fallback={true} />)
    expect(screen.getByTitle(/estimated/i)).toBeInTheDocument()
  })

  test('fallback=false hides estimation annotation', () => {
    render(<SubScoreBar label="Disruption" value={0.9} fallback={false} />)
    expect(screen.queryByTitle(/estimated/i)).not.toBeInTheDocument()
  })
})
