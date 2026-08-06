<script setup>
import { onMounted, ref } from 'vue'
import { useRentalStore } from '../../stores/rentalStore.js'
import { formatDate, formatTL } from '../../utils/format.js'

const props = defineProps({
  vehicleId: { type: Number, required: true },
})

const rentalStore = useRentalStore()
const loading = ref(false)
const error = ref(false)
const rentals = ref([])

async function load() {
  loading.value = true
  error.value = false
  try {
    rentals.value = await rentalStore.fetchVehicleRentalHistory(props.vehicleId)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div v-if="loading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
    <div v-else-if="error" class="rf-glass grid place-items-center rounded-3xl p-12 text-center text-slate-500">
      Kiralama geçmişi yüklenemedi.
    </div>
    <div v-else-if="!rentals.length" class="rf-glass grid place-items-center rounded-3xl p-12 text-center text-slate-500">
      Bu araca ait kiralama kaydı bulunamadı.
    </div>
    <div v-else class="rf-glass-strong overflow-x-auto rounded-3xl">
      <table class="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr class="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
            <th class="py-3 pl-4 pr-3">Sürücü</th>
            <th class="py-3 pr-3">Durum</th>
            <th class="py-3 pr-3">Başlangıç</th>
            <th class="py-3 pr-3">Bitiş</th>
            <th class="py-3 pr-4">Günlük Ücret</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="rental in rentals"
            :key="rental.id"
            class="border-b border-slate-100 last:border-0"
          >
            <td class="py-3 pl-4 pr-3 font-semibold text-slate-900">{{ rental.driver_name }}</td>
            <td class="py-3 pr-3 text-slate-600">{{ rental.status_label }}</td>
            <td class="py-3 pr-3 text-slate-600">{{ formatDate(rental.started_at) }}</td>
            <td class="py-3 pr-3 text-slate-600">{{ formatDate(rental.actual_return_at ?? rental.ended_at) }}</td>
            <td class="py-3 pr-4 font-mono font-semibold tabular-nums text-slate-800">{{ formatTL(rental.daily_rate) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
