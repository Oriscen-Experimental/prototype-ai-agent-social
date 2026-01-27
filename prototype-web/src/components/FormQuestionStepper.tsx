import { useMemo, useState } from 'react'
import type { FormContent, FormQuestion, FormSubmission } from '../lib/agentApi'

export function FormQuestionStepper(props: {
  form: FormContent
  onSubmit: (submission: FormSubmission) => void
}) {
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, unknown>>({})

  const questions = props.form.questions

  const completedQuestions = useMemo(() => {
    return questions.slice(0, currentStep).map((q: FormQuestion) => ({
      param: q.param,
      question: q.question,
      value: answers[q.param],
    }))
  }, [questions, currentStep, answers])

  const currentQuestion = questions[currentStep] ?? null
  const isLastStep = currentStep === questions.length - 1
  const totalSteps = questions.length

  const currentValue = currentQuestion ? answers[currentQuestion.param] : null
  const canProceed = currentValue !== undefined && currentValue !== null && currentValue !== ''

  const handleNext = () => {
    if (!canProceed) return

    if (isLastStep && currentQuestion) {
      // Submit all answers
      props.onSubmit({
        toolName: props.form.toolName,
        toolArgs: props.form.toolArgs,
        answers: answers,
      })
    } else {
      setCurrentStep((s) => s + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1)
    }
  }

  if (questions.length === 0) {
    return <div className="muted">已完成</div>
  }

  return (
    <div className="missingInfoStepper">
      {completedQuestions.length > 0 && (
        <div className="stepperCompleted">
          {completedQuestions.map((q: { param: string; question: string; value: unknown }) => (
            <span key={q.param} className="deckDoneChip">
              {formatValue(q.value)}
            </span>
          ))}
        </div>
      )}

      {currentQuestion && (
        <div className="stepperCard">
          <div className="stepperProgress">
            <span className="muted">
              {currentStep + 1} / {totalSteps}
            </span>
          </div>

          <div className="stepperBody">
            <QuestionField
              question={currentQuestion}
              value={currentValue}
              onChange={(v: unknown) => setAnswers((prev) => ({ ...prev, [currentQuestion.param]: v }))}
            />
          </div>

          <div className="stepperFooter">
            {currentStep > 0 && (
              <button className="btn btnGhost" type="button" onClick={handleBack}>
                上一步
              </button>
            )}
            <button className="btn" type="button" disabled={!canProceed} onClick={handleNext}>
              {isLastStep ? '提交' : '下一步'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function QuestionField(props: {
  question: FormQuestion
  value: unknown
  onChange: (v: unknown) => void
}) {
  const q = props.question
  const options = q.options ?? []

  // If there are options, render as button choices
  if (options.length > 0) {
    return (
      <div className="deckField">
        <div className="deckLabel">{q.question}</div>
        <div className="chipRow">
          {options.map((o: { label: string; value: unknown }, idx: number) => {
            const isSelected = JSON.stringify(props.value) === JSON.stringify(o.value)
            return (
              <button
                key={idx}
                type="button"
                className={isSelected ? 'chip chipActive' : 'chip'}
                onClick={() => props.onChange(o.value)}
              >
                {o.label}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // Otherwise render as text input
  const textValue = typeof props.value === 'string' ? props.value : ''
  return (
    <label className="deckField">
      <div className="deckLabel">{q.question}</div>
      <input
        className="input"
        value={textValue}
        placeholder="Type your answer…"
        onChange={(e) => props.onChange(e.target.value)}
      />
    </label>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if ('label' in obj && typeof obj.label === 'string') return obj.label
    if ('min' in obj && 'max' in obj) return `${obj.min} - ${obj.max}`
    return JSON.stringify(value)
  }
  return String(value)
}
