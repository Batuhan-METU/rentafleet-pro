import { describe, expect, it } from 'vitest'
import { formatTL, formatNumber, formatKm, formatPercent, formatDateShort } from './format.js'

describe('formatTL', () => {
  it('formats a whole number as Turkish lira with no decimals by default', () => {
    expect(formatTL(1500)).toBe('₺1.500')
  })

  it('formats with two decimals when requested', () => {
    expect(formatTL(1500.5, { decimals: true })).toBe('₺1.500,50')
  })

  it('returns an em dash for null/undefined/NaN', () => {
    expect(formatTL(null)).toBe('—')
    expect(formatTL(undefined)).toBe('—')
    expect(formatTL('not-a-number')).toBe('—')
  })
})

describe('formatNumber', () => {
  it('groups thousands with Turkish separators', () => {
    expect(formatNumber(12345)).toBe('12.345')
  })

  it('returns an em dash for missing values', () => {
    expect(formatNumber(null)).toBe('—')
  })
})

describe('formatKm', () => {
  it('appends the km suffix to a grouped number', () => {
    expect(formatKm(12345)).toBe('12.345 km')
  })

  it('returns an em dash for missing values (no dangling suffix)', () => {
    expect(formatKm(null)).toBe('—')
  })
})

describe('formatPercent', () => {
  it('formats with a leading percent sign and one decimal by default', () => {
    expect(formatPercent(12.345)).toBe('%12.3')
  })

  it('respects a custom digit count', () => {
    expect(formatPercent(12.345, { digits: 0 })).toBe('%12')
  })
})

describe('formatDateShort', () => {
  it('formats an ISO date as DD/MM/YYYY', () => {
    expect(formatDateShort('2026-03-05')).toBe('05/03/2026')
  })

  it('returns an em dash for falsy input', () => {
    expect(formatDateShort(null)).toBe('—')
    expect(formatDateShort('')).toBe('—')
  })

  it('falls back to the raw value for an unparsable date', () => {
    expect(formatDateShort('not-a-date')).toBe('not-a-date')
  })
})
