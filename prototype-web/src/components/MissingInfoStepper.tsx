import { useMemo, useState } from 'react'
import type { CardDeck, FormField } from '../lib/agentApi'
import { DeckField, fieldValueFrom, requiredValueOk } from './CardDeck'

type FlatField = FormField & { cardId: string; cardTitle: string }

export function MissingInfoStepper(props: {
  deck: CardDeck
  onSubmit: (cardId: string, data: Record<string, unknown>) => void
}) {
  const [currentStep, setCurrentStep] = useState(0)
  const [values, setValues] = useState<Record<string, unknown>>({})

  const allFields = useMemo<FlatField[]>(() => {
    const result: FlatField[] = []
    for (const card of props.deck.cards) {
      if (card.status === 'completed') continue
      for (const field of card.fields ?? []) {
        result.push({ ...field, cardId: card.id, cardTitle: card.title })
      }
    }
    return result
  }, [props.deck.cards])

  const completedFields = useMemo(() => {
    return allFields.slice(0, currentStep).map((f) => ({
      key: f.key,
      label: f.label,
      value: values[f.key],
    }))
  }, [allFields, currentStep, values])

  const currentField = allFields[currentStep] ?? null
  const isLastStep = currentStep === allFields.length - 1
  const totalSteps = allFields.length

  const currentValue = currentField ? fieldValueFrom(currentField, values) : null
  const canProceed = currentField ? requiredValueOk(currentField, currentValue) : false

  const handleNext = () => {
    if (!canProceed) return

    if (isLastStep && currentField) {
      // 提交所有字段的数据，而不只是当前卡片的字段
      const data: Record<string, unknown> = {}
      for (const f of allFields) {
        data[f.key] = fieldValueFrom(f, values)
      }
      props.onSubmit(currentField.cardId, data)
    } else {
      setCurrentStep((s) => s + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1)
    }
  }

  if (allFields.length === 0) {
    return <div className="muted">已完成</div>
  }

  return (
    <div className="missingInfoStepper">
      {completedFields.length > 0 && (
        <div className="stepperCompleted">
          {completedFields.map((f) => (
            <span key={f.key} className="deckDoneChip">
              {f.label}: {formatValue(f.value)}
            </span>
          ))}
        </div>
      )}

      {currentField && (
        <div className="stepperCard">
          <div className="stepperProgress">
            <span className="muted">
              {currentStep + 1} / {totalSteps}
            </span>
          </div>

          <div className="stepperBody">
            <DeckField
              field={currentField}
              value={currentValue}
              disabled={false}
              onChange={(v) => setValues((prev) => ({ ...prev, [currentField.key]: v }))}
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

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if ('min' in obj && 'max' in obj) return `${obj.min} - ${obj.max}`
    return JSON.stringify(value)
  }
  return String(value)
}
