import { render, screen } from '@testing-library/react'
import AIBriefPanel from '@/components/AIBriefPanel'
import { mockAIExplanation } from './fixtures'

describe('AIBriefPanel', () => {
  test('ai_generated=true renders IBM Granite badge', () => {
    const explanation = mockAIExplanation(true)
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText(/IBM Granite/i)).toBeInTheDocument()
  })

  test('ai_generated=true renders model_id', () => {
    const explanation = mockAIExplanation(true)
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText('ibm/granite-3-8b-instruct')).toBeInTheDocument()
  })

  test('ai_generated=false renders Deterministic Fallback badge', () => {
    const explanation = mockAIExplanation(false)
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText(/Deterministic Fallback/i)).toBeInTheDocument()
  })

  test('ai_generated=false does not show model_id', () => {
    const explanation = mockAIExplanation(false)
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.queryByText('ibm/granite-3-8b-instruct')).not.toBeInTheDocument()
  })

  test('renders headline, explanation, and recommended_action', () => {
    const explanation = mockAIExplanation(true)
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText(explanation.headline)).toBeInTheDocument()
    expect(screen.getByText(explanation.explanation)).toBeInTheDocument()
    expect(screen.getByText(explanation.recommended_action)).toBeInTheDocument()
  })

  test('loading state renders spinner', () => {
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={null}
        loading={true}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText(/generating ai brief/i)).toBeInTheDocument()
  })

  test('null explanation with entityId shows request button', () => {
    render(
      <AIBriefPanel
        title="Get AI Brief for SHP-1002"
        explanation={null}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /ai brief for SHP-1002/i })).toBeInTheDocument()
  })

  test('null entityId shows selection prompt', () => {
    render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={null}
        loading={false}
        entityId={null}
        onRequest={jest.fn()}
      />
    )
    expect(screen.getByText(/select a shipment/i)).toBeInTheDocument()
  })

  test('fallback state is not displayed as an error', () => {
    const explanation = mockAIExplanation(false)
    const { container } = render(
      <AIBriefPanel
        title="Get AI Brief"
        explanation={explanation}
        loading={false}
        entityId="SHP-1002"
        onRequest={jest.fn()}
      />
    )
    // No error role should be present
    expect(container.querySelector('[role="alert"]')).not.toBeInTheDocument()
  })
})
