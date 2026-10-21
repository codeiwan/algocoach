import assert from 'node:assert/strict'
import { substantiallyChangedSinceReview } from '../src/services/coaching-satisfaction.ts'

const reference = `class Solution:\n    def f(self, nums):\n        best = 1\n        current = 1\n        for i in range(1, len(nums)):\n            if nums[i] > nums[i - 1]:\n                current += 1\n            else:\n                current = 1\n            best = max(best, current)\n        return best\n`

assert.equal(substantiallyChangedSinceReview(reference, reference), false)
assert.equal(substantiallyChangedSinceReview(reference, '\n' + reference + '   '), false)
assert.equal(substantiallyChangedSinceReview(reference, reference.replace(' > ', ' >= ')), false)
assert.equal(substantiallyChangedSinceReview(reference, reference.replace('return best', 'return current')), false)
assert.equal(substantiallyChangedSinceReview(reference, ''), true)
assert.equal(substantiallyChangedSinceReview(reference, reference + '\n' + 'print("new branch")\n' + 'assert True\n'), true)
assert.equal(substantiallyChangedSinceReview('a', 'abcdefg'), false)
assert.equal(substantiallyChangedSinceReview('abc'.repeat(10), 'def'.repeat(10)), true)
console.log('Coach proactive-offer suppression: 8 checks passed')
