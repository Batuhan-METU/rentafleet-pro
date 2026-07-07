<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useVehicleStore } from '../stores/vehicleStore.js'
import { useAuthStore } from '../stores/authStore.js'

const props = defineProps({
  vehicle: { type: Object, required: true },
})
const emit = defineEmits(['close', 'edit'])

const store = useVehicleStore()
const auth = useAuthStore()
const {
  currentVehicleScore,
  currentVehicleFuelData,
  currentVehicleAnomalies,
  detailLoading,
  detailError,
} = storeToRefs(store)

const score = computed(() => currentVehicleScore.value?.driver_score ?? null)
const scoreSummary = computed(() => currentVehicleScore.value?.summary ?? null)
const fuel = computed(() => currentVehicleFuelData.value ?? null)
const routeTip = computed(() => fuel.value?.rota_optimizasyonu?.['en_uygun_bölge'] ?? '')

const hasAnomalies = computed(() => currentVehicleAnomalies.value?.anomali_var_mi === true)
const anomalies = computed(() => currentVehicleAnomalies.value?.anomaliler ?? [])

function anomalyLevelClass(level) {
  return level === 'KRITIK'
    ? 'bg-red-100 text-red-700 ring-red-600/30'
    : 'bg-amber-100 text-amber-700 ring-amber-600/30'
}

// Skor rengi: >80 yeşil, 70-80 turuncu, <70 kırmızı.
const scoreTheme = computed(() => {
  const value = score.value
  if (value === null) return { border: 'border-slate-200', text: 'text-slate-400', soft: 'bg-slate-50 text-slate-500' }
  if (value > 80) return { border: 'border-emerald-500', text: 'text-emerald-600', soft: 'bg-emerald-50 text-emerald-700' }
  if (value >= 70) return { border: 'border-amber-500', text: 'text-amber-600', soft: 'bg-amber-50 text-amber-700' }
  return { border: 'border-red-500', text: 'text-red-600', soft: 'bg-red-50 text-red-700' }
})

function close() {
  emit('close')
}

function retry() {
  if (auth.isFleetManager) store.loadVehicleDetail(props.vehicle.id)
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  if (auth.isFleetManager) {
    store.loadVehicleDetail(props.vehicle.id)
  }
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  store.clearVehicleDetail()
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      @click.self="close"
    >
      <!-- Arka plan -->
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>

      <!-- Panel -->
      <div class="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl rf-glass-strong shadow-2xl">
        <div class="rf-accent-bar" />
        <header class="flex items-start justify-between gap-4 border-b border-white/30 px-6 py-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="rounded-xl border border-white/40 bg-white/50 px-2.5 py-1 text-base font-black tracking-wide text-slate-800 backdrop-blur-sm">
              {{ vehicle.plate_number }}
            </span>
            <span v-if="vehicle.sipp_code" class="rf-sipp-pill">{{ vehicle.sipp_code }}</span>
          </div>
          <div class="mt-2 min-w-0">
            <h2 class="text-lg font-black text-slate-900">{{ vehicle.brand }} {{ vehicle.model }}</h2>
            <p v-if="vehicle.sinif_etiketi" class="text-sm font-medium text-brand-700">{{ vehicle.sinif_etiketi }}</p>
            <p v-if="vehicle.sipp_detay" class="text-xs text-slate-500">{{ vehicle.sipp_detay }}</p>
          </div>
          <button
            type="button"
            class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-200 hover:text-slate-700"
            aria-label="Kapat"
            @click="close"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <!-- Gövde -->
        <div class="flex-1 overflow-y-auto px-6 py-6">
          <!-- Yükleniyor -->
          <div v-if="detailLoading" class="grid place-items-center py-16">
            <div class="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
            <p class="mt-4 text-sm font-semibold text-slate-600">Analiz verileri yükleniyor...</p>
          </div>

          <!-- Hata -->
          <div v-else-if="detailError" class="grid place-items-center py-16 text-center">
            <div class="grid h-14 w-14 place-items-center rounded-full bg-red-100 text-2xl font-bold text-red-600">!</div>
            <p class="mt-4 text-base font-bold text-slate-800">Analiz verileri alınamadı</p>
            <p class="mt-1 text-sm text-slate-500">Sunucuya ulaşılamadı. Lütfen tekrar deneyin.</p>
            <button type="button" class="mt-5 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700" @click="retry">
              Tekrar Dene
            </button>
          </div>

          <!-- Operasyon personeli: yalnızca temel bilgi -->
          <div v-else-if="!auth.isFleetManager" class="space-y-4">
            <p class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Detaylı AI analizleri, güvenlik ve fiyatlandırma verileri yalnızca
              <strong>Filo Müdürü</strong> rolüne açıktır.
            </p>
            <dl class="space-y-3 text-sm">
              <div class="flex justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                <dt class="text-slate-500">Durum</dt>
                <dd class="font-semibold text-slate-800">{{ vehicle.statusInfo?.label ?? vehicle.status }}</dd>
              </div>
              <div class="flex justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                <dt class="text-slate-500">Kilometre</dt>
                <dd class="font-semibold text-slate-800">{{ vehicle.current_km?.toLocaleString('tr-TR') }} km</dd>
              </div>
              <div class="flex justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                <dt class="text-slate-500">Üretim Yılı</dt>
                <dd class="font-semibold text-slate-800">{{ vehicle.production_year }}</dd>
              </div>
            </dl>
          </div>

          <!-- Filo müdürü: tam analitik içerik -->
          <div v-else class="space-y-6">
            <!-- Bölüm 1: Güncel kiracı sürüş skoru -->
            <section v-if="score !== null" class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-500">
                <span class="h-2 w-2 rounded-full bg-brand-500"></span> Güncel Kiracı Sürüş Skoru
              </h3>

              <div class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
                <!-- Skor çemberi -->
                <div class="grid h-32 w-32 shrink-0 place-items-center rounded-full border-8 bg-white" :class="scoreTheme.border">
                  <div class="text-center">
                    <p class="text-4xl font-extrabold leading-none" :class="scoreTheme.text">{{ score }}</p>
                    <p class="mt-1 text-xs font-medium text-slate-400">/ 100</p>
                  </div>
                </div>

                <!-- Skor kırılımı -->
                <div class="flex-1 space-y-3">
                  <div class="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                    <span class="text-sm text-slate-600">Toplam Hız İhlali</span>
                    <span class="text-base font-bold text-slate-900">{{ scoreSummary?.toplam_hiz_ihlali ?? 0 }}</span>
                  </div>
                  <div class="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                    <span class="text-sm text-slate-600">Toplam Ani Fren</span>
                    <span class="text-base font-bold text-slate-900">{{ scoreSummary?.toplam_ani_fren ?? 0 }}</span>
                  </div>
                  <div class="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5">
                    <span class="text-sm text-slate-600">Toplam Ani Hızlanma</span>
                    <span class="text-base font-bold text-slate-900">{{ scoreSummary?.toplam_ani_hizlanma ?? 0 }}</span>
                  </div>
                  <div class="flex items-center justify-between rounded-lg px-4 py-2.5" :class="scoreTheme.soft">
                    <span class="text-sm font-medium">Sürüş Yorumu</span>
                    <span class="text-base font-bold">{{ scoreSummary?.surus_yorumu ?? '—' }}</span>
                  </div>
                </div>
              </div>
            </section>
            <p v-else class="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              Bu araca bağlı aktif kiracı bulunmuyor; sürüş skoru sürücü profilinden takip edilir.
            </p>

            <!-- Bölüm 2: AI Yakıt Optimizasyonu -->
            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-500">
                <span class="h-2 w-2 rounded-full bg-emerald-500"></span> AI Yakıt Optimizasyonu
              </h3>

              <div class="grid grid-cols-2 gap-4">
                <div class="rounded-xl bg-blue-50 p-4 text-center">
                  <p class="text-xs font-medium uppercase tracking-wider text-blue-600">İdeal Hız</p>
                  <p class="mt-1 text-3xl font-extrabold text-blue-700">{{ fuel?.ideal_hiz_limiti ?? '—' }}</p>
                  <p class="text-xs text-blue-500">km/s</p>
                </div>
                <div class="rounded-xl bg-emerald-50 p-4 text-center">
                  <p class="text-xs font-medium uppercase tracking-wider text-emerald-600">Tahmini Tasarruf</p>
                  <p class="mt-1 text-3xl font-extrabold text-emerald-700">%{{ fuel?.tahmini_tasarruf_yuzdesi ?? '—' }}</p>
                  <p class="text-xs text-emerald-500">yakıt</p>
                </div>
              </div>

              <!-- AI tavsiyesi -->
              <div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p class="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-amber-700">
                  <span aria-hidden="true">🤖</span> AI Tavsiyesi
                </p>
                <p class="text-sm leading-relaxed text-amber-900">{{ fuel?.ai_tavsiyesi }}</p>
              </div>

              <!-- Rota optimizasyonu -->
              <div class="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p class="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <span aria-hidden="true">🗺️</span> Rota Optimizasyonu
                </p>
                <p class="text-sm leading-relaxed text-slate-700">{{ routeTip }}</p>
              </div>
            </section>

            <!-- Bölüm 3: Güvenlik & Anomaliler -->
            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-500">
                <span class="h-2 w-2 rounded-full bg-red-500"></span> Güvenlik & Anomaliler
              </h3>

              <!-- Kritik uyarı (yanıp sönen) -->
              <div
                v-if="hasAnomalies"
                class="animate-flash mb-4 rounded-xl bg-red-700 px-4 py-3 text-center text-base font-extrabold text-white"
              >
                🚨 KRİTİK GÜVENLİK İHLALİ TESPİT EDİLDİ!
              </div>

              <!-- Anomali listesi -->
              <ul v-if="hasAnomalies" class="space-y-3">
                <li
                  v-for="(anomaly, index) in anomalies"
                  :key="index"
                  class="rounded-xl border border-slate-200 bg-white p-4"
                >
                  <div class="mb-1.5 flex items-center justify-between gap-2">
                    <span class="font-bold text-slate-800">{{ anomaly.tip }}</span>
                    <span
                      class="rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset"
                      :class="anomalyLevelClass(anomaly.seviye)"
                    >
                      {{ anomaly.seviye }}
                    </span>
                  </div>
                  <p class="text-sm leading-relaxed text-slate-700">{{ anomaly.mesaj }}</p>
                  <p class="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                    <span aria-hidden="true">🕒</span> {{ anomaly.tarih }}
                  </p>
                </li>
              </ul>

              <!-- Temiz durum -->
              <div
                v-else
                class="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3"
              >
                <span class="grid h-8 w-8 place-items-center rounded-full bg-emerald-500 text-white">✓</span>
                <p class="text-sm font-semibold text-emerald-800">Güvenlik ihlali tespit edilmedi. Araç temiz.</p>
              </div>
            </section>
          </div>
        </div>

        <!-- Alt bar -->
        <footer class="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button
            v-if="auth.isFleetManager"
            type="button"
            class="mr-auto rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-100"
            @click="emit('edit', vehicle)"
          >
            Maliyet Bilgilerini Düzenle
          </button>
          <button
            type="button"
            class="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            @click="close"
          >
            Kapat
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
