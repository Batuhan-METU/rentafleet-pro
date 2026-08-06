<script setup>
// Canlı filo haritası (Leaflet + OpenStreetMap) — Day 10.
// Pinia store'daki liveVehicles'ı (Day 9, 5 sn'de bir güncellenir) tüketir;
// her aracı renkli marker olarak çizer, Türkçe popup gösterir ve Day 6 kritik
// anomalisi olan araçları yanıp sönen koyu kırmızı ile vurgular.
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useVehicleLiveTrackingStore } from '../stores/vehicleLiveTrackingStore.js'
import { VEHICLE_STATUS_LABELS } from '../utils/vehicleStatus.js'

const store = useVehicleLiveTrackingStore()

const ANKARA = [39.9334, 32.8597]
const SPEEDING_KMH = 120

// Durum kodu -> harita pin rengi. Etiket metni ../utils/vehicleStatus.js'den
// (TEK kaynak); pin rengi bu bileşene özel bir görsel seçimdir.
const STATUS = {
  AVAILABLE: { color: '#10b981', label: VEHICLE_STATUS_LABELS.AVAILABLE },
  RENTED: { color: '#3b82f6', label: VEHICLE_STATUS_LABELS.RENTED },
  MAINTENANCE: { color: '#f59e0b', label: VEHICLE_STATUS_LABELS.MAINTENANCE },
}
const CRITICAL_COLOR = '#991b1b'

const mapEl = ref(null)
let map = null
let markers = {} // { [id]: { marker, sig } }
let didFit = false

const lastUpdate = ref(null)

// Haritada gösterilebilen (konumu olan) araçlar.
const trackable = computed(() =>
  store.liveVehicles.filter((v) => v.latitude != null && v.longitude != null),
)
const movingCount = computed(() => trackable.value.filter((v) => v.speed > 0).length)
const rentedCount = computed(() => trackable.value.filter((v) => v.status_code === 'RENTED').length)
const criticalCount = computed(() => trackable.value.filter((v) => v.critical_anomaly).length)

function vehicleColor(v) {
  if (v.critical_anomaly) return CRITICAL_COLOR
  return STATUS[v.status_code]?.color ?? '#64748b'
}

function makeIcon(v) {
  const cls = 'rf-marker' + (v.critical_anomaly ? ' rf-marker--critical' : '')
  return L.divIcon({
    className: '',
    html: `<div class="${cls}" style="background:${vehicleColor(v)}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  })
}

function popupHtml(v) {
  const status = STATUS[v.status_code]
  const critical = v.critical_anomaly
    ? `<div style="margin-top:6px;padding:4px 8px;border-radius:6px;background:#fee2e2;color:#991b1b;font-weight:700;font-size:11px">🚨 KRİTİK ANOMALİ</div>`
    : ''
  return `
    <div style="min-width:190px;font-family:system-ui">
      <div style="font-weight:700;font-size:13px;color:#0f172a">${v.plate_number}</div>
      <div style="color:#64748b;font-size:12px;margin-bottom:6px">${v.brand_model_segment || v.brand_model}</div>
      <div style="font-size:12px;line-height:1.7">
        <div>Güncel Durum: <b style="color:${status?.color ?? '#64748b'}">${v.status_label}</b></div>
        <div>Hız: <b${v.speed > SPEEDING_KMH ? ' style="color:#dc2626"' : ''}>${v.speed} km/s</b></div>
        <div>Yakıt Durumu: <b>%${v.fuel_level ?? '—'}</b></div>
      </div>
      ${critical}
    </div>`
}

function syncMarkers() {
  if (!map) return
  const seen = new Set()

  for (const v of trackable.value) {
    seen.add(v.id)
    const latlng = [v.latitude, v.longitude]
    const sig = `${v.status_code}|${v.critical_anomaly}`
    const entry = markers[v.id]

    if (entry) {
      entry.marker.setLatLng(latlng)
      entry.marker.setPopupContent(popupHtml(v))
      if (entry.sig !== sig) {
        entry.marker.setIcon(makeIcon(v)) // renk/kritik durumu değiştiyse ikonu yenile
        entry.sig = sig
      }
    } else {
      const marker = L.marker(latlng, { icon: makeIcon(v) })
        .bindPopup(popupHtml(v))
        .addTo(map)
      markers[v.id] = { marker, sig }
    }
  }

  // Akıştan düşen araçların marker'larını kaldır.
  for (const id of Object.keys(markers)) {
    if (!seen.has(Number(id))) {
      map.removeLayer(markers[id].marker)
      delete markers[id]
    }
  }

  if (!didFit && trackable.value.length) {
    map.fitBounds(L.latLngBounds(trackable.value.map((v) => [v.latitude, v.longitude])), {
      padding: [50, 50],
      maxZoom: 13,
    })
    didFit = true
  }

  if (trackable.value.length) lastUpdate.value = new Date()
}

watch(() => store.liveVehicles, syncMarkers, { deep: true })

onMounted(() => {
  map = L.map(mapEl.value, { zoomControl: true }).setView(ANKARA, 11)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  }).addTo(map)

  store.initLiveTracking()
  syncMarkers()
})

onBeforeUnmount(() => {
  store.stopLiveTracking()
  if (map) {
    map.remove()
    map = null
  }
  markers = {}
})

const lastUpdateText = computed(() =>
  lastUpdate.value
    ? lastUpdate.value.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—',
)
</script>

<template>
  <div class="flex h-[calc(100vh-9rem)] flex-col gap-4">
    <!-- Üst bilgi şeridi -->
    <div class="rf-glass-strong flex flex-wrap items-center gap-2 rounded-3xl p-3">
      <div class="flex items-center gap-2 rounded-2xl bg-emerald-50 px-4 py-2.5">
        <span class="rf-live-dot" />
        <span class="text-sm font-black text-emerald-700">Canlı</span>
      </div>

      <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-2">
        <p class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Takip</p>
        <p class="text-xl font-black leading-tight text-slate-900">{{ trackable.length }}</p>
      </div>

      <div class="rounded-2xl bg-emerald-50 px-4 py-2">
        <p class="text-[10px] font-bold uppercase tracking-wide text-emerald-700/70">Hareket</p>
        <p class="text-xl font-black leading-tight text-emerald-700">{{ movingCount }}</p>
      </div>

      <div class="rounded-2xl bg-blue-50 px-4 py-2">
        <p class="text-[10px] font-bold uppercase tracking-wide text-blue-700/70">Kirada</p>
        <p class="text-xl font-black leading-tight text-blue-700">{{ rentedCount }}</p>
      </div>

      <div
        class="rounded-2xl px-4 py-2 transition-colors"
        :class="criticalCount ? 'bg-red-50 ring-1 ring-red-300/50' : 'bg-slate-900/[0.03]'"
      >
        <p class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide" :class="criticalCount ? 'text-red-700/80' : 'text-slate-400'">
          <span v-if="criticalCount" class="h-1.5 w-1.5 rounded-full bg-red-600 animate-pulse" />
          Kritik
        </p>
        <p class="text-xl font-black leading-tight" :class="criticalCount ? 'text-red-700' : 'text-slate-900'">{{ criticalCount }}</p>
      </div>

      <div class="ml-auto flex items-center gap-4">
        <div class="hidden items-center gap-3 text-xs text-slate-600 lg:flex">
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-emerald-500"></span>{{ STATUS.AVAILABLE.label }}</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-blue-500"></span>{{ STATUS.RENTED.label }}</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-amber-500"></span>{{ STATUS.MAINTENANCE.label }}</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-red-800"></span>Kritik</span>
        </div>
        <span class="text-xs font-medium text-slate-400">Son güncelleme: {{ lastUpdateText }}</span>
      </div>
    </div>

    <!-- Harita -->
    <div class="rf-glass-strong relative flex-1 overflow-hidden rounded-3xl ring-1 ring-white/40">
      <div ref="mapEl" class="h-full w-full"></div>

      <div
        v-if="!trackable.length"
        class="pointer-events-none absolute inset-0 z-[1000] grid place-items-center bg-white/60 backdrop-blur-sm"
      >
        <div class="pointer-events-auto max-w-sm rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-lg">
          <div class="mx-auto grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-2xl">🛰️</div>
          <p class="mt-3 font-semibold text-slate-800">Henüz canlı veri yok</p>
          <p class="mt-1 text-sm text-slate-500">
            Araçların haritada görünmesi için simülatörü başlatın:
          </p>
          <code class="mt-3 block rounded-lg bg-slate-900 px-3 py-2 text-left text-xs text-emerald-300">
            python3 manage.py run_simulator
          </code>
        </div>
      </div>
    </div>
  </div>
</template>
