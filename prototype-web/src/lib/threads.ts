import type { CaseId, ChatMessage, ChatThread, Profile } from '../types'
import { readJson, writeJson } from './storage'

const KEY = 'proto.threads.v1'

type Store = Record<string, ChatThread>

function now() {
  return Date.now()
}

function id() {
  return `${now()}_${Math.random().toString(16).slice(2)}`
}

export function makeThreadId(caseId: CaseId, profileId: string) {
  return `${caseId}__${profileId}`
}

export function parseThreadId(threadId: string): { caseId: CaseId; profileId: string } | null {
  const [caseId, profileId] = threadId.split('__')
  if (!caseId || !profileId) return null
  if (caseId !== 'drink' && caseId !== 'comfort' && caseId !== 'talk-ai') return null
  return { caseId, profileId }
}

export function readThreads(): Store {
  return readJson<Store>(KEY, {})
}

export function writeThreads(store: Store) {
  writeJson(KEY, store)
}

export function upsertThread(thread: ChatThread) {
  const store = readThreads()
  store[thread.threadId] = thread
  writeThreads(store)
}

export function appendMessage(threadId: string, message: ChatMessage) {
  const store = readThreads()
  const t = store[threadId]
  if (!t) return
  store[threadId] = { ...t, messages: [...t.messages, message] }
  writeThreads(store)
}

export function ensureThread(args: { caseId: CaseId; profile: Profile; seed?: ChatMessage[] }): ChatThread {
  const threadId = makeThreadId(args.caseId, args.profile.id)
  const store = readThreads()
  const existing = store[threadId]
  if (existing) return existing
  const initial: ChatMessage[] = [
    { id: id(), role: 'system', text: '这是一个原型：聊天/约日历均为 mock。', at: now() },
    ...(args.seed ?? []),
  ]
  const created: ChatThread = {
    threadId,
    caseId: args.caseId,
    profileId: args.profile.id,
    profileKind: args.profile.kind,
    title: args.profile.name,
    messages: initial,
  }
  store[threadId] = created
  writeThreads(store)
  return created
}

export function makeMeMessage(text: string): ChatMessage {
  return { id: id(), role: 'me', text, at: now() }
}

export function makeOtherMessage(text: string): ChatMessage {
  return { id: id(), role: 'other', text, at: now() }
}

export function makeSystemMessage(text: string): ChatMessage {
  return { id: id(), role: 'system', text, at: now() }
}

