import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useVehicleStore } from '../stores/vehicleStore.js'

/**
 * Araç store'unu React hook tarzında, sade bir arayüzle sunan composable.
 *
 * Bileşenler Pinia/Axios detaylarını hiç bilmeden sadece şunu yapar:
 *   const { vehicles, loading, error, refresh } = useVehicles()
 *
 * @param {{ immediate?: boolean }} options
 *   immediate=true ise bileşen mount olduğunda veri otomatik çekilir.
 */
export function useVehicles({ immediate = true } = {}) {
  const store = useVehicleStore()

  // storeToRefs, state ve getter'ları reaktifliği koruyarak ref'e çevirir.
  const { localizedVehicles, loading, error, vehicleCount, statusCounts } = storeToRefs(store)

  const fetchVehicles = () => store.fetchVehicles()

  if (immediate) {
    onMounted(() => {
      // Veri zaten yüklüyse (ör. görünüm değişimi) tekrar istek atma.
      if (store.vehicles.length === 0) {
        fetchVehicles()
      }
    })
  }

  return {
    // Türkçeleştirilmiş, statusInfo ile zenginleştirilmiş araç listesi.
    vehicles: localizedVehicles,
    loading,
    error,
    vehicleCount,
    statusCounts,
    fetchVehicles,
    refresh: fetchVehicles,
  }
}
