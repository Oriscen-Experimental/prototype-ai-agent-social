import { useEffect, useMemo, useState } from 'react'
import type { OnboardingData } from '../types'
import { readJson, removeKey, subscribe, writeJson } from './storage'

const KEY = 'proto.onboarding.v1'

type Stored = { completed: boolean; data: OnboardingData | null }

const fallback: Stored = { completed: false, data: null }

export function useOnboarding() {
  const [stored, setStored] = useState<Stored>(() => readJson(KEY, fallback))

  useEffect(() => subscribe(() => setStored(readJson(KEY, fallback))), [])

  return useMemo(() => {
    return {
      isCompleted: stored.completed,
      data: stored.data,
      complete: (data: OnboardingData) => writeJson<Stored>(KEY, { completed: true, data }),
      reset: () => removeKey(KEY),
    }
  }, [stored])
}

