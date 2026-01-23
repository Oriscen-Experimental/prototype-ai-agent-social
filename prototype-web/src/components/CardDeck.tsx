import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { Card, CardDeck, FormField } from '../lib/agentApi'

function asNumberOrNull(value: unknown): number | null {
  if (typeof value !== 'number') return null
  if (!Number.isFinite(value)) return null
  return value
}

function isNonEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length > 0
  return Boolean(value)
}

function requiredValueOk(field: FormField, value: unknown): boolean {
  if (field.required === false) return true
  if (field.type === 'range') {
    const v = (typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {}) as Record<string, unknown>
    const min = asNumberOrNull(v.min)
    const max = asNumberOrNull(v.max)
    return min !== null && max !== null && min <= max
  }
  return isNonEmpty(value)
}

function fieldValueFrom(field: FormField, draft: Record<string, unknown>) {
  if (Object.prototype.hasOwnProperty.call(draft, field.key)) return draft[field.key]
  return field.value
}

export function CardDeckView(props: {
  deck: CardDeck
  onSubmitCard: (cardId: string, data: Record<string, unknown>) => void
}) {
  const [drafts, setDrafts] = useState<Record<string, Record<string, unknown>>>({})
  const scrollerRef = useRef<HTMLDivElement | null>(null)

  const activeId = props.deck.activeCardId ?? props.deck.cards.find((c) => c.status === 'active')?.id ?? null
  const activeIndex = useMemo(() => (activeId ? props.deck.cards.findIndex((c) => c.id === activeId) : -1), [activeId, props.deck.cards])

  useEffect(() => {
    if (!scrollerRef.current) return
    if (activeIndex < 0) return
    const left = Math.max(0, activeIndex * 170 - 24)
    scrollerRef.current.scrollTo({ left, behavior: 'smooth' })
  }, [activeIndex])

  const zIndexFor = (c: Card, idx: number) => {
    if (c.status === 'active') return 1000
    if (c.status === 'upcoming') return 500 - idx
    return 100 - idx
  }

  const leftFor = (idx: number) => idx * 170

  const deckWidth = useMemo(() => Math.max(1, props.deck.cards.length) * 170 + 220, [props.deck.cards.length])

  return (
    <div className="deckWrap">
      <div className="deckScroller" ref={scrollerRef}>
        <div className="deck" style={{ width: deckWidth }}>
          {props.deck.cards.map((card, idx) => (
            <DeckCard
              key={card.id}
              card={card}
              isActive={card.id === activeId}
              style={{
                transform: `translate(${leftFor(idx)}px, ${card.status === 'completed' ? 22 : card.id === activeId ? 0 : 12}px)`,
                zIndex: zIndexFor(card, idx),
              }}
              draft={drafts[card.id] ?? {}}
              onDraftChange={(next) => setDrafts((prev) => ({ ...prev, [card.id]: next }))}
              onSubmit={(data) => props.onSubmitCard(card.id, data)}
            />
          ))}
        </div>
      </div>
      <div className="muted">Tip: fill the front card and click ✅. Completed cards slide back; the next card comes forward.</div>
    </div>
  )
}

function DeckCard(props: {
  card: Card
  isActive: boolean
  style: CSSProperties
  draft: Record<string, unknown>
  onDraftChange: (next: Record<string, unknown>) => void
  onSubmit: (data: Record<string, unknown>) => void
}) {
  const fields = props.card.fields ?? []
  const requiredFields = fields.filter((f) => f.required !== false)
  const draft = props.draft

  const canSubmit = useMemo(() => {
    if (!props.isActive) return false
    if (props.card.status === 'completed') return false
    return requiredFields.every((f) => requiredValueOk(f, fieldValueFrom(f, draft)))
  }, [props.isActive, props.card.status, requiredFields, draft])

  const cardClass =
    props.card.status === 'completed'
      ? 'deckCard deckCardDone'
      : props.isActive
        ? 'deckCard deckCardActive'
        : props.card.status === 'upcoming'
          ? 'deckCard deckCardUpcoming'
          : 'deckCard'

  return (
    <div className={cardClass} style={props.style}>
      <div className="deckCardHeader">
        <div className="deckCardTitle">{props.card.title}</div>
        {props.card.status === 'completed' ? <div className="deckCardCheck">✓</div> : null}
      </div>

      <div className="deckCardBody">
        {fields.map((f) => (
          <DeckField
            key={f.key}
            field={f}
            value={fieldValueFrom(f, draft)}
            disabled={!props.isActive || props.card.status === 'completed'}
            onChange={(v) => props.onDraftChange({ ...draft, [f.key]: v })}
          />
        ))}
      </div>

      <div className="deckCardFooter">
        <button
          className="btn"
          type="button"
          disabled={!canSubmit}
          onClick={() => {
            if (!canSubmit) return
            const data: Record<string, unknown> = {}
            for (const f of fields) data[f.key] = fieldValueFrom(f, draft)
            props.onSubmit(data)
          }}
        >
          ✅
        </button>
      </div>
    </div>
  )
}

function DeckField(props: {
  field: FormField
  value: unknown
  disabled: boolean
  onChange: (v: unknown) => void
}) {
  const f = props.field
  const required = f.required !== false
  const label = `${f.label}${required ? ' *' : ''}`

  if (f.type === 'multi_select') {
    const selected = Array.isArray(props.value) ? (props.value as string[]) : []
    const options = f.options ?? []
    return (
      <div className="deckField">
        <div className="deckLabel">{label}</div>
        <div className="chipRow">
          {options.map((o) => {
            const active = selected.includes(o.value)
            return (
              <button
                key={o.value}
                type="button"
                className={active ? 'chip chipActive' : 'chip'}
                disabled={props.disabled}
                onClick={() => {
                  if (props.disabled) return
                  props.onChange(active ? selected.filter((x) => x !== o.value) : [...selected, o.value])
                }}
              >
                {o.label}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  if (f.type === 'select') {
    const options = f.options ?? []
    const value = typeof props.value === 'string' ? props.value : ''
    return (
      <label className="deckField">
        <div className="deckLabel">{label}</div>
        <select className="select" value={value} disabled={props.disabled} onChange={(e) => props.onChange(e.target.value)}>
          <option value="">{f.placeholder ?? 'Select…'}</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    )
  }

  if (f.type === 'number') {
    const parsed = props.value == null ? Number.NaN : Number(props.value)
    const value: string | number =
      typeof props.value === 'number' && Number.isFinite(props.value) ? props.value : Number.isFinite(parsed) ? parsed : ''
    return (
      <label className="deckField">
        <div className="deckLabel">{label}</div>
        <input
          className="input"
          type="number"
          value={value}
          min={f.min ?? undefined}
          max={f.max ?? undefined}
          disabled={props.disabled}
          placeholder={(f.placeholder ?? '') || undefined}
          onChange={(e) => {
            const raw = e.target.value
            if (raw === '') props.onChange(null)
            else props.onChange(Number(raw))
          }}
        />
      </label>
    )
  }

  if (f.type === 'range') {
    const v = (typeof props.value === 'object' && props.value !== null ? (props.value as Record<string, unknown>) : {}) as Record<
      string,
      unknown
    >
    const currentMin = asNumberOrNull(v.min)
    const currentMax = asNumberOrNull(v.max)
    const minVal: string | number = currentMin ?? ''
    const maxVal: string | number = currentMax ?? ''
    return (
      <div className="deckField">
        <div className="deckLabel">{label}</div>
        <div className="rangeRow">
          <input
            className="input"
            type="number"
            value={minVal}
            min={f.min ?? undefined}
            max={f.max ?? undefined}
            disabled={props.disabled}
            placeholder="min"
            onChange={(e) => {
              const raw = e.target.value
              const nextMin = raw === '' ? null : Number(raw)
              props.onChange({ min: nextMin, max: currentMax })
            }}
          />
          <div className="muted">to</div>
          <input
            className="input"
            type="number"
            value={maxVal}
            min={f.min ?? undefined}
            max={f.max ?? undefined}
            disabled={props.disabled}
            placeholder="max"
            onChange={(e) => {
              const raw = e.target.value
              const nextMax = raw === '' ? null : Number(raw)
              props.onChange({ min: currentMin, max: nextMax })
            }}
          />
        </div>
      </div>
    )
  }

  const value = typeof props.value === 'string' ? props.value : props.value == null ? '' : String(props.value)
  return (
    <label className="deckField">
      <div className="deckLabel">{label}</div>
      <input
        className="input"
        value={value}
        disabled={props.disabled}
        placeholder={(f.placeholder ?? '') || undefined}
        onChange={(e) => props.onChange(e.target.value)}
      />
    </label>
  )
}
