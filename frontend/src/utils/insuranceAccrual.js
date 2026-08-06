// Poliçe tipine göre TAHAKKUK EDEN sigorta tutarı — backend'in
// insurance_cost_service.accrued_insurance_for_vehicle (§3.4) ile BİREBİR
// aynı formül: poliçe başına tutar/365 × geçen gün (start-exclusive/
// end-inclusive), süresi dolmuş son poliçe "aynı oranla yenilenmiş" kabul
// edilir. Hem Araç Detayı'ndaki "Gelir & Gider Özeti" hem de "Poliçeler"
// sekmesi AYNI fonksiyonu kullanır — aksi halde iki yerde ayrı yazılmış
// aynı hesap zamanla birbirinden sapar (bu, tam olarak yaşanan karışıklığın
// sebebiydi: poliçe kartındaki TAM prim ile özetteki KISMİ tahakkuk farklı
// görünüyordu, açıklama olmadan).
function periodDays(start, end) {
  const days = (end.getTime() - start.getTime()) / 86400000
  return days > 0 ? Math.round(days) : 0
}

function accruedInsuranceByTypeAsOf(policies, asOf) {
  const totals = { COMPREHENSIVE: 0, LIABILITY: 0, GREEN_CARD: 0 }
  const byType = {}
  for (const p of policies) {
    if (!(p.policy_type in totals)) continue
    ;(byType[p.policy_type] ??= []).push(p)
  }
  for (const [type, list] of Object.entries(byType)) {
    const sorted = [...list].sort((a, b) => new Date(a.start_date) - new Date(b.start_date))
    let total = 0
    for (const policy of sorted) {
      const start = new Date(policy.start_date)
      const end = new Date(policy.end_date)
      if (start > asOf) continue
      const accrualEnd = end < asOf ? end : asOf
      const dailyRate = Number(policy.amount) / 365
      total += dailyRate * periodDays(start, accrualEnd)
    }
    const last = sorted[sorted.length - 1]
    if (last) {
      const lastEnd = new Date(last.end_date)
      if (asOf > lastEnd) {
        const dailyRate = Number(last.amount) / 365
        total += dailyRate * periodDays(lastEnd, asOf)
      }
    }
    totals[type] = total
  }
  return totals
}

// Seçili yılın SONUNDAKİ (ya da içinde bulunduğumuz yıl için bugünkü) iki
// anlık görüntünün farkı — backend'in build_vehicle_yearly_summary'sinin
// aynı deseni, poliçe tipine göre kırılımıyla.
export function accruedInsuranceByTypeForYear(policies, year) {
  const yearEnd = new Date(year, 11, 31)
  const today = new Date()
  const periodEnd = yearEnd < today ? yearEnd : today
  const dayBeforeStart = new Date(year - 1, 11, 31)

  const after = accruedInsuranceByTypeAsOf(policies, periodEnd)
  const before = accruedInsuranceByTypeAsOf(policies, dayBeforeStart)
  const result = {}
  for (const type of Object.keys(after)) {
    result[type] = Math.round((after[type] - before[type]) * 100) / 100
  }
  return result
}
