import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

// Araçların öngörücü bakım durumu — vehicleStore'dan ayrı, çünkü araç
// CRUD/listeleme ile hiçbir state paylaşmayan bağımsız bir kaygı
// (audit bulgusu #21).
export const useVehicleMaintenanceStore = defineStore('vehicleMaintenance', {
  state: () => ({
    // Öngörücü bakım durumları — tüm araçlar (sağlıklı dahil).
    maintenanceAlerts: [],
    maintenanceCounts: { healthy: 0, warning: 0, critical: 0 },
    maintenanceLoading: false,
  }),

  actions: {
    // Öngörücü bakım durumlarını çeker (tüm araçlar, sağlıklı dahil).
    async fetchMaintenanceAlerts() {
      this.maintenanceLoading = true
      try {
        const { data } = await apiClient.get('vehicles/maintenance-alerts/')
        this.maintenanceAlerts = data.vehicles ?? []
        this.maintenanceCounts = {
          healthy: data.healthy_count ?? 0,
          warning: data.warning_count ?? 0,
          critical: data.critical_count ?? 0,
        }
      } catch {
        // Uyarılar gösterilemez; ekranın geri kalanı çalışmaya devam eder.
      } finally {
        this.maintenanceLoading = false
      }
    },
  },
})
