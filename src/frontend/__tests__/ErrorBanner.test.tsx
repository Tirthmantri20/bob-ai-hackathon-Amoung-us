import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ErrorBanner from '@/components/ErrorBanner'

describe('ErrorBanner', () => {
  test('renders error message', () => {
    render(<ErrorBanner message="Backend unavailable — start FastAPI on port 8000." />)
    expect(screen.getByText(/Backend unavailable/i)).toBeInTheDocument()
  })

  test('has role="alert"', () => {
    render(<ErrorBanner message="Something failed" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  test('retry button calls onRetry', async () => {
    const onRetry = jest.fn()
    render(<ErrorBanner message="Failed" onRetry={onRetry} />)
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  test('no retry button when onRetry not provided', () => {
    render(<ErrorBanner message="No retry here" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
