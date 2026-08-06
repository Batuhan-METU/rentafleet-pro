import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUiStore } from './uiStore.js'

function setHash(hash) {
  window.location.hash = hash
}

beforeEach(() => {
  setActivePinia(createPinia())
  window.history.replaceState(null, '', '/')
})

describe('parseHash', () => {
  it('parses a vehicle detail URL', () => {
    setHash('#/vehicles/42')
    const ui = useUiStore()
    expect(ui.parseHash(true)).toEqual({
      view: 'vehicle-detail',
      vehicleId: 42,
      driverId: null,
      loanId: null,
    })
  })

  it('parses a driver detail URL', () => {
    setHash('#/drivers/7')
    const ui = useUiStore()
    expect(ui.parseHash(true)).toEqual({
      view: 'driver-detail',
      vehicleId: null,
      driverId: 7,
      loanId: null,
    })
  })

  it('parses a loan detail URL', () => {
    setHash('#/loans/3')
    const ui = useUiStore()
    expect(ui.parseHash(true)).toEqual({
      view: 'loan-detail',
      vehicleId: null,
      driverId: null,
      loanId: 3,
    })
  })

  it('falls back to overview for managers on an empty hash', () => {
    setHash('')
    const ui = useUiStore()
    expect(ui.parseHash(true).view).toBe('overview')
  })

  it('falls back to vehicles for non-managers on an empty hash', () => {
    setHash('')
    const ui = useUiStore()
    expect(ui.parseHash(false).view).toBe('vehicles')
  })

  it('redirects a non-manager away from a manager-only view', () => {
    setHash('#/pricing')
    const ui = useUiStore()
    expect(ui.parseHash(false).view).toBe('vehicles')
  })

  it('passes through a manager-only view for a manager', () => {
    setHash('#/pricing')
    const ui = useUiStore()
    expect(ui.parseHash(true).view).toBe('pricing')
  })
})

describe('open/close detail actions', () => {
  it('opening a vehicle detail sets the hash and clears other detail ids', () => {
    const ui = useUiStore()
    ui.activeDriverId = 99
    ui.openVehicleDetail(42)
    expect(ui.activeView).toBe('vehicle-detail')
    expect(ui.activeVehicleId).toBe(42)
    expect(ui.activeDriverId).toBeNull()
    expect(window.location.hash).toBe('#/vehicles/42')
  })

  it('closing a vehicle detail returns to the list view', () => {
    const ui = useUiStore()
    ui.openVehicleDetail(42)
    ui.closeVehicleDetail()
    expect(ui.activeView).toBe('vehicles')
    expect(ui.activeVehicleId).toBeNull()
    expect(window.location.hash).toBe('#/vehicles')
  })

  it('opening a driver detail clears any open vehicle detail', () => {
    const ui = useUiStore()
    ui.openVehicleDetail(42)
    ui.openDriverDetail(7)
    expect(ui.activeView).toBe('driver-detail')
    expect(ui.activeDriverId).toBe(7)
    expect(ui.activeVehicleId).toBeNull()
    expect(window.location.hash).toBe('#/drivers/7')
  })

  it('opening a loan detail with a null id is a no-op', () => {
    const ui = useUiStore()
    ui.openLoanDetail(null)
    expect(ui.activeView).toBe('overview')
    expect(ui.activeLoanId).toBeNull()
  })
})
