// rental_economics_service ile aynı maliyet matematiği (önizleme / simülasyon).

export const PLANNING_HORIZON_DAYS = 365
export const DEFAULT_MONTHLY_MAINTENANCE = 2500
export const ESTIMATED_INSURANCE_PCT = 0.045
export const ESTIMATED_MTV_PCT = 0.012

function round2(n) {
  return Math.round(n * 100) / 100
}

/**
 * @param {object} inputs
 * @returns {object|null}
 */
export function computeCostCard(inputs) {
  const purchase = Number(inputs.purchase_price) || 0
  if (purchase <= 0) return null

  const kasko = Number(inputs.annual_kasko) || 0
  const traffic = Number(inputs.annual_traffic) || 0
  let annualInsurance
  if (kasko > 0 || traffic > 0) {
    annualInsurance = kasko + traffic
  } else {
    const combined = Number(inputs.annual_insurance) || 0
    annualInsurance = combined > 0 ? combined : purchase * ESTIMATED_INSURANCE_PCT
  }

  let mtv = Number(inputs.annual_mtv) || 0
  if (mtv <= 0) mtv = purchase * ESTIMATED_MTV_PCT

  const inspection = Number(inputs.annual_inspection) || 0
  let maintenance = Number(inputs.monthly_maintenance) || 0
  if (maintenance <= 0) maintenance = DEFAULT_MONTHLY_MAINTENANCE

  const prep = Number(inputs.rental_prep) || 0
  const monthly = annualInsurance / 12 + mtv / 12 + inspection / 12 + maintenance
  const annualOperating = monthly * 12
  const annualBurden = purchase + prep + annualOperating
  const dailyCost = annualBurden / PLANNING_HORIZON_DAYS
  const days = Math.max(Number(inputs.rental_days) || 1, 1)

  return {
    purchase_price: purchase,
    rental_prep_cost: prep,
    annual_insurance: round2(annualInsurance),
    annual_mtv: round2(mtv),
    annual_inspection: round2(inspection),
    monthly_maintenance: round2(maintenance),
    monthly_operating: round2(monthly),
    annual_operating: round2(annualOperating),
    annual_burden: round2(annualBurden),
    daily_cost: round2(dailyCost),
    period_floor: round2(dailyCost * days),
    rental_days: days,
  }
}

/** decision.maliyet_dagilimi → simülasyon başlangıç değerleri */
export function seedSimulationFromDecision(decision, rentalDays) {
  const d = decision?.maliyet_dagilimi
  if (!d) return null
  return {
    purchase_price: d.alis_fiyati ?? 0,
    rental_prep: d.kiraya_hazirlik ?? 0,
    annual_kasko: d.yillik_kasko ?? 0,
    annual_traffic: d.yillik_trafik_sigortasi ?? 0,
    annual_insurance: d.yillik_sigorta ?? 0,
    annual_mtv: d.yillik_mtv ?? 0,
    annual_inspection: d.yillik_muayene ?? 0,
    monthly_maintenance: d.aylik_bakim ?? 0,
    rental_days: rentalDays ?? decision?.ozet?.kiralanan_gun ?? 1,
  }
}

/** Simülasyon → PATCH /vehicles/<id>/ gövdesi */
export function simulationToVehiclePatch(sim) {
  const kasko = Number(sim.annual_kasko) || 0
  const traffic = Number(sim.annual_traffic) || 0
  const payload = {
    purchase_price: Number(sim.purchase_price) || 0,
    initial_industrial_expense: Number(sim.rental_prep) || 0,
    annual_mtv_cost: Number(sim.annual_mtv) || 0,
    annual_inspection_cost: Number(sim.annual_inspection) || 0,
    estimated_monthly_maintenance: Number(sim.monthly_maintenance) || 0,
  }
  if (kasko > 0 || traffic > 0) {
    payload.annual_kasko_cost = kasko
    payload.annual_traffic_insurance_cost = traffic
  } else if (Number(sim.annual_insurance) > 0) {
    payload.annual_kasko_cost = Number(sim.annual_insurance)
    payload.annual_traffic_insurance_cost = 0
  }
  return payload
}
