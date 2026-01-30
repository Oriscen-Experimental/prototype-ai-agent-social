import { useEffect, useMemo, useState } from 'react'
import type { FormContent, FormQuestion, FormQuestionOption, FormSubmission } from '../lib/agentApi'

type AnswerNode = {
  param: string
  value: unknown
  displayLabel: string
}

/**
 * Derive the current question to display based on root questions and answer path.
 * Returns null if we've reached a leaf node (complete).
 */
function deriveCurrentQuestion(
  rootQuestions: FormQuestion[],
  answerPath: AnswerNode[]
): FormQuestion | null {
  if (rootQuestions.length === 0) return null

  // Start from root
  let currentLevel: FormQuestion[] = rootQuestions
  let questionIndex = 0

  // Walk down the path
  for (const ans of answerPath) {
    const q = currentLevel.find((q) => q.param === ans.param)
    if (!q) return null

    // Find the selected option (by matching value)
    const selectedOpt = q.options.find(
      (o) => JSON.stringify(o.value) === JSON.stringify(ans.value)
    )

    // If option has followUp, descend into it
    if (selectedOpt?.followUp && selectedOpt.followUp.length > 0) {
      currentLevel = selectedOpt.followUp
      questionIndex = 0
    } else {
      // This was a terminal selection for this question
      // Check if there are more questions at this level
      const idx = currentLevel.findIndex((q) => q.param === ans.param)
      const remaining = currentLevel.slice(idx + 1)
      if (remaining.length > 0) {
        currentLevel = remaining
        questionIndex = 0
      } else {
        // No more questions - we're complete
        return null
      }
    }
  }

  return currentLevel[questionIndex] ?? null
}

/**
 * Collect all answers from the path, skipping null values (followUp placeholders).
 */
function collectAnswers(answerPath: AnswerNode[]): Record<string, unknown> {
  const answers: Record<string, unknown> = {}
  for (const node of answerPath) {
    if (node.value !== null && node.value !== undefined) {
      answers[node.param] = node.value
    }
  }
  return answers
}

export function FormQuestionStepper(props: {
  form: FormContent
  onSubmit: (submission: FormSubmission) => void
}) {
  const [answerPath, setAnswerPath] = useState<AnswerNode[]>([])

  const { currentQuestion, isComplete } = useMemo(() => {
    const q = deriveCurrentQuestion(props.form.questions, answerPath)
    return {
      currentQuestion: q,
      isComplete: q === null && answerPath.length > 0,
    }
  }, [props.form.questions, answerPath])

  const handleSelectOption = (option: FormQuestionOption) => {
    if (!currentQuestion) return

    const node: AnswerNode = {
      param: currentQuestion.param,
      value: option.value,
      displayLabel: option.label,
    }

    setAnswerPath((prev) => [...prev, node])
  }

  // Track the current text input value separately (not in answerPath until submitted)
  const [pendingTextValue, setPendingTextValue] = useState('')

  const handleTextInput = (value: string) => {
    setPendingTextValue(value)
  }

  const handleTextSubmit = () => {
    if (!currentQuestion || !pendingTextValue.trim()) return

    const node: AnswerNode = {
      param: currentQuestion.param,
      value: pendingTextValue.trim(),
      displayLabel: pendingTextValue.trim(),
    }

    setAnswerPath((prev) => [...prev, node])
    setPendingTextValue('')
  }

  const handleBack = () => {
    setAnswerPath((prev) => prev.slice(0, -1))
  }

  const handleBreadcrumbClick = (index: number) => {
    setAnswerPath((prev) => prev.slice(0, index))
  }

  const handleSubmit = () => {
    const answers = collectAnswers(answerPath)
    props.onSubmit({
      toolName: props.form.toolName,
      toolArgs: props.form.toolArgs,
      answers,
    })
  }

  // Auto-submit when all questions are answered
  useEffect(() => {
    if (isComplete) {
      handleSubmit()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isComplete])

  if (props.form.questions.length === 0) {
    return <div className="muted">No questions to answer</div>
  }

  const canSubmitText = pendingTextValue.trim() !== ''

  return (
    <div className="missingInfoStepper">
      {/* Breadcrumb of completed answers */}
      {answerPath.length > 0 && (
        <div className="stepperCompleted">
          {answerPath.map((node, idx) => (
            <button
              key={`${node.param}-${idx}`}
              type="button"
              className="deckDoneChip"
              onClick={() => handleBreadcrumbClick(idx)}
              title="Click to go back to this step"
            >
              {node.displayLabel || '-'}
            </button>
          ))}
        </div>
      )}

      {/* Current question card */}
      {currentQuestion && !isComplete && (
        <div className="stepperCard">
          <div className="stepperBody">
            {currentQuestion.options.length > 0 ? (
              <OptionQuestionField
                question={currentQuestion}
                onSelect={handleSelectOption}
              />
            ) : (
              <TextQuestionField
                question={currentQuestion}
                value={pendingTextValue}
                onChange={handleTextInput}
                onSubmit={handleTextSubmit}
              />
            )}
          </div>

          <div className="stepperFooter">
            {answerPath.length > 0 && (
              <button className="btn btnGhost" type="button" onClick={handleBack}>
                Back
              </button>
            )}
            {/* For text input, show a Next/Submit button */}
            {currentQuestion.options.length === 0 && (
              <button
                className="btn"
                type="button"
                disabled={!canSubmitText}
                onClick={handleTextSubmit}
              >
                Next
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Renders options as clickable chips. Selecting an option immediately advances.
 */
function OptionQuestionField(props: {
  question: FormQuestion
  onSelect: (option: FormQuestionOption) => void
}) {
  const q = props.question

  return (
    <div className="deckField">
      <div className="deckLabel">{q.question}</div>
      <div className="chipRow">
        {q.options.map((o, idx) => (
          <button
            key={idx}
            type="button"
            className="chip"
            onClick={() => props.onSelect(o)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Renders a text input field.
 */
function TextQuestionField(props: {
  question: FormQuestion
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
}) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && props.value.trim()) {
      props.onSubmit()
    }
  }

  return (
    <label className="deckField">
      <div className="deckLabel">{props.question.question}</div>
      <input
        className="input"
        value={props.value}
        placeholder="Type your answer…"
        onChange={(e) => props.onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
    </label>
  )
}
