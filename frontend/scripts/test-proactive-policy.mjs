import assert from 'node:assert/strict'

import { evaluateProactiveOffer } from '../src/services/proactive-coaching-policy.ts'

const base = {
  nowMs: 150_000,
  startedAtMs: 0,
  lastEditedAtMs: 0,
  currentRevision: 5,
  hasCode: true,
  autoEnabled: true,
  busy: false,
  offerPending: false,
  hintCount: 0,
  lastOfferAtMs: null,
  lastOfferRevision: null,
  lastOfferHintCount: null,
  lastDeclineAtMs: null,
  lastDeclinedRevision: null,
  stableEdits: [],
}

const check = evaluateProactiveOffer

assert.equal(check(base), 'idle')

assert.equal(check({ ...base, lastEditedAtMs: 145_000 }), null)

assert.equal(check({ ...base, autoEnabled: false }), null)

assert.equal(check({ ...base, busy: true }), null)

assert.equal(check({ ...base, hintCount: 3 }), null)

assert.equal(check({ ...base, lastDeclineAtMs: 100_000 }), null)

assert.equal(check({ ...base, lastDeclinedRevision: 5 }), null)

assert.equal(check({ ...base, lastOfferAtMs: 100_000 }), null)

assert.equal(
  check({
    ...base,
    lastOfferRevision: 5,
    lastOfferHintCount: 0,
  }),
  null,
)

assert.equal(
  check({
    ...base,
    lastOfferRevision: 5,
    lastOfferHintCount: 0,
    hintCount: 1,
  }),
  'idle',
)

const repeatedEdits = [
  { atMs: 80_000, codeLength: 120 },
  { atMs: 98_000, codeLength: 125 },
  { atMs: 116_000, codeLength: 122 },
  { atMs: 130_000, codeLength: 121 },
]

assert.equal(
  check({
    ...base,
    lastEditedAtMs: 130_000,
    stableEdits: repeatedEdits,
  }),
  'repeated_edits',
)

assert.equal(
  check({
    ...base,
    hasCode: false,
    lastEditedAtMs: 40_000,
  }),
  null,
)

console.log('Proactive coaching policy: 12 checks passed')
