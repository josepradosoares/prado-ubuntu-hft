import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatPrice,
  formatSignedNumber,
  formatSignedPercent,
  isFiniteNumber,
  sanitizeChartPoints,
} from '../src/utils/formatters.ts'

describe('safe numeric formatters', () => {
  it('detects finite numbers properly', () => {
    assert.equal(isFiniteNumber(0), true)
    assert.equal(isFiniteNumber(-3.14), true)
    assert.equal(isFiniteNumber(undefined), false)
    assert.equal(isFiniteNumber(null), false)
    assert.equal(isFiniteNumber(Number.NaN), false)
    assert.equal(isFiniteNumber(Number.POSITIVE_INFINITY), false)
  })

  it('returns "--" instead of throwing or inventing 0 on missing values', () => {
    assert.equal(formatNumber(undefined, 2), '--')
    assert.equal(formatNumber(null, 2), '--')
    assert.equal(formatNumber(Number.NaN, 2), '--')
    assert.equal(formatNumber(Number.POSITIVE_INFINITY, 2), '--')
    assert.equal(formatPrice(undefined, 4), '--')
    assert.equal(formatPercent(undefined, 1, true), '--')
    assert.equal(formatSignedNumber(null, 2), '--')
    assert.equal(formatSignedPercent(undefined, 1, true), '--')
    assert.equal(formatCurrency(undefined, 'USD'), '--')
  })

  it('formats valid numbers accurately', () => {
    assert.equal(formatNumber(1.845, 2), '1.84')
    assert.equal(formatPrice(1234.5, 4), '1234.5000')
    assert.equal(formatPercent(0.352, 1, true), '35.2%')
    assert.equal(formatSignedNumber(1.23, 2), '+1.23')
    assert.equal(formatSignedNumber(-1.23, 2), '-1.23')
    assert.equal(formatSignedPercent(0.25, 1, true), '+25.0%')
  })

  it('sanitizes chart points by filtering invalid entries and sorting by time', () => {
    const raw = [
      { time: 200, price: 10, vwap: 10, upper_2: 11, lower_2: 9 },
      { time: 150, price: undefined, vwap: 10, upper_2: 11, lower_2: 9 },
      null,
      { time: 100, price: 9.5, vwap: 9.6, upper_2: 10.5, lower_2: 8.7 },
      { time: 200, price: 10.2, vwap: 10.1, upper_2: 11.1, lower_2: 9.1 },
    ]
    const result = sanitizeChartPoints(raw)
    assert.equal(result.length, 2)
    assert.equal(result[0].time, 100)
    assert.equal(result[1].time, 200)
    assert.equal(result[1].price, 10.2)
  })
})
