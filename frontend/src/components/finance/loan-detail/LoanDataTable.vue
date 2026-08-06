<script setup>
// Paylaşılan kredi-detay tablosu — Taksit Listesi ve Kredi Araç Listesi
// sekmelerinin ikisi de bu tek bileşeni kullanır (§ Kredi Detay Sayfası).
// Arama + tarih aralığı filtresi + sıralanabilir sütunlar + sütun
// göster/gizle + adlandırılmış filtre şablonları (localStorage, kişisel
// görünüm tercihi — sunucu tarafı gerektirmez).
import { computed, ref, watch } from 'vue'
import DatePicker from '../../vehicle-form/DatePicker.vue'
import { useClickOutside } from '../../../composables/useClickOutside.js'
import {
  LOAN_TABLE_COLUMNS_PREFIX as COLUMNS_PREFIX,
  LOAN_TABLE_TEMPLATES_PREFIX as TEMPLATES_PREFIX,
} from '../../../utils/storageKeys.js'

const props = defineProps({
  rows: { type: Array, required: true },
  columns: { type: Array, required: true }, // [{ key, label, align, formatter?(row) }]
  searchKeys: { type: Array, default: () => [] },
  dateFilterKey: { type: String, default: '' },
  storageKey: { type: String, required: true },
  rowKey: { type: String, default: 'id' },
})

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}
function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* localStorage dolu/kapalı olabilir — sessizce yoksay */
  }
}

const searchText = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const sortKey = ref('')
const sortDir = ref('asc') // 'asc' | 'desc'

const searchInputEl = ref(null)
const showDatePopover = ref(false)
const showColumnsMenu = ref(false)
const showTemplatesMenu = ref(false)
const newTemplateName = ref('')
const rootEl = ref(null)

const visibleColumns = ref(
  new Set(readJson(COLUMNS_PREFIX + props.storageKey, props.columns.map((c) => c.key))),
)
watch(
  visibleColumns,
  (v) => writeJson(COLUMNS_PREFIX + props.storageKey, Array.from(v)),
  { deep: true },
)

const templates = ref(readJson(TEMPLATES_PREFIX + props.storageKey, []))
watch(templates, (v) => writeJson(TEMPLATES_PREFIX + props.storageKey, v), { deep: true })

function toggleColumn(key) {
  const next = new Set(visibleColumns.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  visibleColumns.value = next
}

const visibleColumnList = computed(() =>
  props.columns.filter((c) => visibleColumns.value.has(c.key)),
)

function toggleSort(key) {
  if (sortKey.value !== key) {
    sortKey.value = key
    sortDir.value = 'asc'
  } else if (sortDir.value === 'asc') {
    sortDir.value = 'desc'
  } else {
    sortKey.value = ''
    sortDir.value = 'asc'
  }
}

function cellValue(row, key) {
  return key.split('.').reduce((acc, part) => acc?.[part], row)
}

const normalizedSearch = computed(() => searchText.value.trim().toLocaleLowerCase('tr'))

const filteredRows = computed(() => {
  let list = props.rows
  const q = normalizedSearch.value
  if (q) {
    list = list.filter((row) =>
      props.searchKeys.some((key) =>
        String(cellValue(row, key) ?? '').toLocaleLowerCase('tr').includes(q),
      ),
    )
  }
  if (props.dateFilterKey && (dateFrom.value || dateTo.value)) {
    list = list.filter((row) => {
      const raw = cellValue(row, props.dateFilterKey)
      if (!raw) return false
      const value = String(raw).slice(0, 10)
      if (dateFrom.value && value < dateFrom.value) return false
      if (dateTo.value && value > dateTo.value) return false
      return true
    })
  }
  return list
})

const sortedRows = computed(() => {
  if (!sortKey.value) return filteredRows.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...filteredRows.value].sort((a, b) => {
    const av = cellValue(a, sortKey.value)
    const bv = cellValue(b, sortKey.value)
    if (av == null && bv == null) return 0
    if (av == null) return -1 * dir
    if (bv == null) return 1 * dir
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv), 'tr') * dir
  })
})

const dateRangeLabel = computed(() => {
  if (!dateFrom.value && !dateTo.value) return ''
  const fmt = (d) => {
    if (!d) return '…'
    const [y, m, day] = d.split('-')
    return `${day}.${m}.${y}`
  }
  return `${fmt(dateFrom.value)} – ${fmt(dateTo.value)}`
})

function clearDateFilter() {
  dateFrom.value = ''
  dateTo.value = ''
  showDatePopover.value = false
}

function currentViewState() {
  return {
    search: searchText.value,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
    sortKey: sortKey.value,
    sortDir: sortDir.value,
    visibleColumns: Array.from(visibleColumns.value),
  }
}

function saveTemplate() {
  const name = newTemplateName.value.trim()
  if (!name) return
  const withoutSameName = templates.value.filter((t) => t.name !== name)
  templates.value = [...withoutSameName, { name, state: currentViewState() }]
  newTemplateName.value = ''
}

function applyTemplate(tpl) {
  const s = tpl.state
  searchText.value = s.search ?? ''
  dateFrom.value = s.dateFrom ?? ''
  dateTo.value = s.dateTo ?? ''
  sortKey.value = s.sortKey ?? ''
  sortDir.value = s.sortDir ?? 'asc'
  visibleColumns.value = new Set(s.visibleColumns ?? props.columns.map((c) => c.key))
  showTemplatesMenu.value = false
}

function deleteTemplate(tpl) {
  templates.value = templates.value.filter((t) => t.name !== tpl.name)
}

useClickOutside(rootEl, () => {
  showDatePopover.value = false
  showColumnsMenu.value = false
  showTemplatesMenu.value = false
})
</script>

<template>
  <div ref="rootEl" class="space-y-3">
    <!-- Araç çubuğu -->
    <div class="flex flex-wrap items-center gap-2">
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
        </svg>
        <input
          ref="searchInputEl"
          v-model="searchText"
          type="search"
          placeholder="Herhangi bir şey arayın"
          class="rf-input w-64 !pl-9"
        />
      </div>

      <div class="relative">
        <button
          type="button"
          class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-500 transition-colors hover:border-slate-300"
          @click="showDatePopover = !showDatePopover"
        >
          <span :class="dateRangeLabel ? 'text-slate-800' : 'text-slate-400'">
            {{ dateRangeLabel || 'Tarih ile filtreleyin' }}
          </span>
          <svg class="h-4 w-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
        </button>

        <div
          v-if="showDatePopover"
          class="absolute z-30 mt-1.5 w-72 rounded-xl border border-slate-200 bg-white p-4 shadow-xl"
        >
          <p class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Başlangıç</p>
          <DatePicker v-model="dateFrom" />
          <p class="mb-2 mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">Bitiş</p>
          <DatePicker v-model="dateTo" />
          <div class="mt-4 flex justify-between">
            <button type="button" class="text-xs font-semibold text-slate-400 hover:text-slate-600" @click="clearDateFilter">
              Temizle
            </button>
            <button type="button" class="rf-btn-primary !px-3 !py-1.5 !text-xs" @click="showDatePopover = false">
              Uygula
            </button>
          </div>
        </div>
      </div>

      <button
        type="button"
        class="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-rose-500 transition-colors hover:border-slate-300"
        title="Ara"
        @click="searchInputEl?.focus()"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
        </svg>
      </button>

      <div class="ml-auto flex items-center gap-2">
        <div class="relative">
          <button
            type="button"
            class="rf-btn-secondary !px-4 !py-2 !text-xs"
            @click="showColumnsMenu = !showColumnsMenu; showTemplatesMenu = false"
          >
            <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 4.5v15m6-15v15M4.5 6.75h15a1.5 1.5 0 001.5-1.5v-.75a1.5 1.5 0 00-1.5-1.5h-15A1.5 1.5 0 003 4.5v.75a1.5 1.5 0 001.5 1.5zm0 12.75h15a1.5 1.5 0 001.5-1.5v-9a1.5 1.5 0 00-1.5-1.5h-15A1.5 1.5 0 003 9v9a1.5 1.5 0 001.5 1.5z" />
            </svg>
            Sütunlar
          </button>
          <div
            v-if="showColumnsMenu"
            class="absolute right-0 z-30 mt-1.5 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
          >
            <label
              v-for="col in columns"
              :key="col.key"
              class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                :checked="visibleColumns.has(col.key)"
                class="h-3.5 w-3.5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                @change="toggleColumn(col.key)"
              />
              {{ col.label }}
            </label>
          </div>
        </div>

        <div class="relative">
          <button
            type="button"
            class="rf-btn-secondary !px-4 !py-2 !text-xs"
            @click="showTemplatesMenu = !showTemplatesMenu; showColumnsMenu = false"
          >
            <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 4.5h18M6 9h12M9 13.5h6M11 18h2" />
            </svg>
            Filtre Şablonları
          </button>
          <div
            v-if="showTemplatesMenu"
            class="absolute right-0 z-30 mt-1.5 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-xl"
          >
            <p class="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-400">Kayıtlı Şablonlar</p>
            <p v-if="!templates.length" class="mb-3 text-xs text-slate-400">Henüz kaydedilmiş şablon yok.</p>
            <ul v-else class="mb-3 max-h-40 space-y-1 overflow-y-auto">
              <li
                v-for="tpl in templates"
                :key="tpl.name"
                class="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50"
              >
                <button type="button" class="flex-1 truncate text-left font-semibold text-slate-700" @click="applyTemplate(tpl)">
                  {{ tpl.name }}
                </button>
                <button type="button" class="shrink-0 text-slate-300 hover:text-rose-600" title="Sil" @click="deleteTemplate(tpl)">
                  <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </li>
            </ul>
            <div class="flex items-center gap-1.5 border-t border-slate-100 pt-2">
              <input
                v-model="newTemplateName"
                type="text"
                placeholder="Şablon adı…"
                class="rf-input !py-1.5 !text-xs"
                @keydown.enter="saveTemplate"
              />
              <button type="button" class="rf-btn-primary !px-2.5 !py-1.5 !text-xs" @click="saveTemplate">Kaydet</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tablo -->
    <div v-if="sortedRows.length" class="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table class="w-full text-left text-sm">
        <thead class="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-400">
          <tr>
            <th
              v-for="col in visibleColumnList"
              :key="col.key"
              class="cursor-pointer select-none whitespace-nowrap px-4 py-3 transition-colors hover:text-slate-600"
              :class="col.align === 'right' ? 'text-right' : 'text-left'"
              @click="toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1" :class="col.align === 'right' ? 'flex-row-reverse' : ''">
                {{ col.label }}
                <svg
                  v-if="sortKey === col.key && sortDir === 'asc'"
                  class="h-3 w-3 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
                ><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>
                <svg
                  v-else-if="sortKey === col.key && sortDir === 'desc'"
                  class="h-3 w-3 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
                ><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                <svg
                  v-else
                  class="h-3 w-3 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
                ><path stroke-linecap="round" stroke-linejoin="round" d="M8 9l4-4 4 4m0 6l-4 4-4-4" /></svg>
              </span>
            </th>
            <th v-if="$slots['row-extra']" class="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedRows"
            :key="row[rowKey]"
            class="border-t border-slate-100 transition-colors hover:bg-slate-50/80"
          >
            <td
              v-for="col in visibleColumnList"
              :key="col.key"
              class="px-4 py-3 text-slate-700"
              :class="col.align === 'right' ? 'text-right' : 'text-left'"
            >
              {{ col.formatter ? col.formatter(row) : cellValue(row, col.key) }}
            </td>
            <td v-if="$slots['row-extra']" class="px-4 py-3 text-right">
              <slot name="row-extra" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center">
      <div class="grid h-20 w-20 place-items-center rounded-full bg-slate-50">
        <svg class="h-10 w-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="mt-4 text-base font-bold text-slate-700">Veriler bulunamadı</p>
      <p class="mt-1 text-sm text-slate-400">
        {{ rows.length ? 'Lütfen filtreleme seçeneklerinizi değiştiriniz.' : 'Bu kredi için henüz kayıt yok.' }}
      </p>
    </div>
  </div>
</template>
