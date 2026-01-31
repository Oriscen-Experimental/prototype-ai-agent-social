import { useCallback, useSyncExternalStore } from 'react'
import type { PlannerModel } from './agentApi'
import { readJson, subscribe, writeJson } from './storage'

const PLANNER_MODEL_KEY = 'plannerModel'
const DEFAULT_MODEL: PlannerModel = 'medium'

export const PLANNER_OPTIONS: { value: PlannerModel; label: string }[] = [
  { value: 'light', label: 'light and fast' },
  { value: 'medium', label: 'medium' },
  { value: 'heavy', label: 'heavy and slow' },
]

function getPlannerModel(): PlannerModel {
  return readJson<PlannerModel>(PLANNER_MODEL_KEY, DEFAULT_MODEL)
}

export function usePlannerModel() {
  const model = useSyncExternalStore(subscribe, getPlannerModel)
  const setModel = useCallback((m: PlannerModel) => {
    writeJson(PLANNER_MODEL_KEY, m)
  }, [])
  return { model, setModel }
}

