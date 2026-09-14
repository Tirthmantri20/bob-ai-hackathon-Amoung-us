import { render, screen } from '@testing-library/react'
import SeverityBadge from '@/components/SeverityBadge'

describe('SeverityBadge', () => {
  test('CRITICAL renders red class and label', () => {
    const { container } = render(<SeverityBadge severity="CRITICAL" />)
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('bg-red-600')
  })

  test('HIGH renders orange class and label', () => {
    const { container } = render(<SeverityBadge severity="HIGH" />)
    expect(screen.getByText('HIGH')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('bg-orange-500')
  })

  test('MEDIUM renders yellow class and label', () => {
    const { container } = render(<SeverityBadge severity="MEDIUM" />)
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('bg-yellow-400')
  })

  test('LOW renders green class and label', () => {
    const { container } = render(<SeverityBadge severity="LOW" />)
    expect(screen.getByText('LOW')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('bg-green-600')
  })

  test('OK renders green-500 class', () => {
    const { container } = render(<SeverityBadge severity="OK" />)
    expect(container.firstChild).toHaveClass('bg-green-500')
  })

  test('WARNING renders amber class', () => {
    const { container } = render(<SeverityBadge severity="WARNING" />)
    expect(container.firstChild).toHaveClass('bg-amber-500')
  })

  test('UNKNOWN severity renders gray fallback', () => {
    const { container } = render(<SeverityBadge severity="UNKNOWN" />)
    expect(container.firstChild).toHaveClass('bg-gray-400')
  })

  test('unrecognized severity renders gray fallback', () => {
    const { container } = render(<SeverityBadge severity="WHATEVER" />)
    expect(container.firstChild).toHaveClass('bg-gray-400')
  })

  test('text label is always present alongside color', () => {
    render(<SeverityBadge severity="CRITICAL" />)
    // Text is always shown — color is never the sole differentiator
    expect(screen.getByText('CRITICAL')).toBeVisible()
  })

  test('aria-label includes severity value', () => {
    render(<SeverityBadge severity="HIGH" />)
    expect(screen.getByLabelText(/Severity: HIGH/i)).toBeInTheDocument()
  })
})
