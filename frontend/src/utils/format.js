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

// "12.345 km" — VehicleListRow/MaintenanceCenter/MaintenanceVehicleCard'da
// bağımsız birer `Intl.NumberFormat('tr-TR')` + "km" ekleyen sarmalayıcı
// olarak tekrarlanıyordu.
export function formatKm(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${numberFormatter.format(value)} km`
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

// Alıştığımız gün/ay/yıl (GG/AA/YYYY) biçimi — formatDate'in kısa ay adıyla
// yazdığı biçimden farklı, tarihin tamamen rakamla/eğik çizgiyle istendiği
// yerler için (ör. Araç Detayı bilgi kartları).
export function formatDateShort(value) {
  if (!value) return '—'
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    const day = String(d.getDate()).padStart(2, '0')
    const month = String(d.getMonth() + 1).padStart(2, '0')
    return `${day}/${month}/${d.getFullYear()}`
  } catch {
    return value
  }
}
