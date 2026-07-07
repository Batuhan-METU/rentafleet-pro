// Türkçe biçimlendirme yardımcıları (para, yüzde, tarih).

const tlFormatter = new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency: 'TRY',
  maximumFractionDigits: 0,
})

const tlFormatterDecimal = new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency: 'TRY',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const numberFormatter = new Intl.NumberFormat('tr-TR')

export function formatTL(value, { decimals = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return decimals ? tlFormatterDecimal.format(value) : tlFormatter.format(value)
}

export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return numberFormatter.format(value)
}

export function formatPercent(value, { digits = 1 } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `%${Number(value).toFixed(digits)}`
}

export function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleDateString('tr-TR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return value
  }
}
