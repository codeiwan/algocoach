import assert from 'node:assert/strict'

import {
  AUTO_WINDOW_MS,
  evaluateAutoAnalysisBudget as evaluate,
} from '../src/services/autonomous-analysis-policy.ts'

assert.equal(
  evaluate(0, [], 0).allowed,
  true,
  'first request',
)

assert.equal(
  evaluate(10_000, [0], 1).waitMs,
  15_000,
  'normal cooldown',
)

assert.equal(
  evaluate(10_000, [0], 1, true).waitMs,
  2_000,
  'priority recheck',
)

assert.equal(
  evaluate(25_000, [0], 1).allowed,
  true,
  'cooldown elapsed',
)

assert.equal(
  evaluate(11_999, [0], 1, true).allowed,
  false,
  'priority still throttled',
)

assert.equal(
  evaluate(12_000, [0], 1, true).allowed,
  true,
  'priority ready',
)

assert.equal(
  evaluate(100_000, [0], 24).reason,
  'SESSION_BUDGET',
  'session budget',
)

const eight = [
  0,
  30_000,
  60_000,
  90_000,
  120_000,
  150_000,
  180_000,
  210_000,
]

assert.equal(
  evaluate(240_000, eight, 8).reason,
  'WINDOW_BUDGET',
  'window budget',
)

assert.equal(
  evaluate(AUTO_WINDOW_MS, eight, 8).allowed,
  true,
  'window expiry',
)

assert.equal(
  evaluate(AUTO_WINDOW_MS - 1, eight, 8).waitMs,
  1,
  'resume at expiry',
)

console.log(
  'Autonomous analysis policy: 10 checks passed',
)
