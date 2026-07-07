<script setup>
// Canlı filo haritası (Leaflet + OpenStreetMap) — Day 10.
// Pinia store'daki liveVehicles'ı (Day 9, 5 sn'de bir güncellenir) tüketir;
// her aracı renkli marker olarak çizer, Türkçe popup gösterir ve Day 6 kritik
// anomalisi olan araçları yanıp sönen koyu kırmızı ile vurgular.
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useVehicleStore } from '../stores/vehicleStore.js'

const store = useVehicleStore()

const ANKARA = [39.9334, 32.8597]
const SPEEDING_KMH = 120

// Durum kodu -> renk + Türkçe etiket.
const STATUS = {
  AVAILABLE: { color: '#10b981', label: 'Müsait' },
  RENTED: { color: '#3b82f6', label: 'Kirada' },
  MAINTENANCE: { color: '#f59e0b', label: 'Bakımda' },
}
const CRITICAL_COLOR = '#991b1b'

const mapEl = ref(null)
let map = null
let markers = {} // { [id]: { marker, sig } }
let didFit = false

const lastUpdate = ref(null)

// Haritada gösterilebilen (konumu olan) araçlar.
const trackable = computed(() =>
  store.liveVehicles.filter((v) => v.enlem != null && v.boylam != null),
)
const movingCount = computed(() => trackable.value.filter((v) => v.hiz > 0).length)
const rentedCount = computed(() => trackable.value.filter((v) => v.durum_kodu === 'RENTED').length)
const criticalCount = computed(() => trackable.value.filter((v) => v.kritik_anomali).length)

function vehicleColor(v) {
  if (v.kritik_anomali) return CRITICAL_COLOR
  return STATUS[v.durum_kodu]?.color ?? '#64748b'
}

function makeIcon(v) {
  const cls = 'rf-marker' + (v.kritik_anomali ? ' rf-marker--critical' : '')
  return L.divIcon({
    className: '',
    html: `<div class="${cls}" style="background:${vehicleColor(v)}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  })
}

function popupHtml(v) {
  const status = STATUS[v.durum_kodu]
  const critical = v.kritik_anomali
    ? `<div style="margin-top:6px;padding:4px 8px;border-radius:6px;background:#fee2e2;color:#991b1b;font-weight:700;font-size:11px">🚨 KRİTİK ANOMALİ</div>`
    : ''
  return `
    <div style="min-width:190px;font-family:system-ui">
      <div style="font-weight:700;font-size:13px;color:#0f172a">${v.plaka}</div>
      <div style="color:#64748b;font-size:12px;margin-bottom:6px">${v.marka_model_sinif || v.marka_model}</div>
      <div style="font-size:12px;line-height:1.7">
        <div>Güncel Durum: <b style="color:${status?.color ?? '#64748b'}">${v.durum}</b></div>
        <div>Hız: <b${v.hiz > SPEEDING_KMH ? ' style="color:#dc2626"' : ''}>${v.hiz} km/s</b></div>
        <div>Yakıt Durumu: <b>%${v.yakit_seviyesi ?? '—'}</b></div>
      </div>
      ${critical}
    </div>`
}

function syncMarkers() {
  if (!map) return
  const seen = new Set()

  for (const v of trackable.value) {
    seen.add(v.id)
    const latlng = [v.enlem, v.boylam]
    const sig = `${v.durum_kodu}|${v.kritik_anomali}`
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
    map.fitBounds(L.latLngBounds(trackable.value.map((v) => [v.enlem, v.boylam])), {
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
    <div class="flex flex-wrap items-center gap-2">
      <div class="rf-capsule !py-2 flex items-center gap-2">
        <span class="rf-live-dot" />
        <span class="text-sm font-bold text-slate-800">Canlı</span>
      </div>

      <div class="rf-capsule !py-2">
        <span class="text-sm text-slate-500/80">Takip:</span>
        <span class="ml-1 text-sm font-black text-slate-900">{{ trackable.length }}</span>
      </div>

      <div class="rf-capsule !py-2">
        <span class="text-sm text-slate-500/80">Hareket:</span>
        <span class="ml-1 text-sm font-black text-emerald-600">{{ movingCount }}</span>
      </div>

      <div class="rf-capsule !py-2">
        <span class="text-sm text-slate-500/80">Kirada:</span>
        <span class="ml-1 text-sm font-black text-blue-600">{{ rentedCount }}</span>
      </div>

      <div
        class="rf-capsule !py-2"
        :class="criticalCount ? 'ring-1 ring-red-300/40' : ''"
      >
        <span class="text-sm text-slate-500/80">Kritik:</span>
        <span class="ml-1 text-sm font-black" :class="criticalCount ? 'text-red-700' : 'text-slate-900'">{{ criticalCount }}</span>
      </div>

      <div class="ml-auto flex items-center gap-4">
        <div class="hidden items-center gap-3 text-xs text-slate-600 lg:flex">
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-emerald-500"></span>Müsait</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-blue-500"></span>Kirada</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-amber-500"></span>Bakımda</span>
          <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-full bg-red-800"></span>Kritik</span>
        </div>
        <span class="text-xs text-slate-400">Son güncelleme: {{ lastUpdateText }}</span>
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
