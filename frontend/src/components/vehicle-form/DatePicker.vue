<script setup>
// Native <input type="date"> takvim açılır penceresinin dili tarayıcı/OS
// diline bağlıdır, garanti Türkçe ay ismi vermez — bu yüzden sıfırdan,
// her zaman Türkçe bir takvim widget'ı yazıldı. v-model YYYY-MM-DD string
// (backend'in beklediği format) ile çalışır.
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const MONTHS_TR = [
  'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık',
]
const DAYS_TR = ['Pt', 'Sa', 'Ça', 'Pe', 'Cu', 'Ct', 'Pz']

// Ay/yıl için tıklayarak (ok tuşlarıyla ileri geri gitmek yerine) doğrudan
// seçim — doğum tarihi gibi onlarca yıl geriye gidilmesi gereken alanlarda
// "‹" okuna yüzlerce kez basmak pratik değil. Yıl aralığı hem geçmişe
// (doğum tarihi) hem geleceğe (poliçe/sözleşme tarihleri) yetecek genişlikte.
const CURRENT_YEAR = new Date().getFullYear()
const YEARS = Array.from({ length: 111 }, (_, i) => CURRENT_YEAR + 10 - i)

const open = ref(false)
const rootEl = ref(null)

function parseDate(str) {
  if (!str) return null
  const [y, m, d] = str.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

const selected = computed(() => parseDate(props.modelValue))
const viewDate = ref(selected.value ?? new Date())

watch(selected, (d) => {
  if (d) viewDate.value = new Date(d)
})

const displayText = computed(() => {
  const d = selected.value
  if (!d) return ''
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
})

const calendarDays = computed(() => {
  const year = viewDate.value.getFullYear()
  const month = viewDate.value.getMonth()
  const firstOfMonth = new Date(year, month, 1)
  const startOffset = (firstOfMonth.getDay() + 6) % 7 // Pazartesi = 0
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < startOffset; i++) cells.push(null)
  for (let day = 1; day <= daysInMonth; day++) cells.push(new Date(year, month, day))
  return cells
})

function isSameDay(a, b) {
  return !!a && !!b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function pick(day) {
  if (!day) return
  const y = day.getFullYear()
  const m = String(day.getMonth() + 1).padStart(2, '0')
  const d = String(day.getDate()).padStart(2, '0')
  emit('update:modelValue', `${y}-${m}-${d}`)
  open.value = false
}

function prevMonth() {
  viewDate.value = new Date(viewDate.value.getFullYear(), viewDate.value.getMonth() - 1, 1)
}
function nextMonth() {
  viewDate.value = new Date(viewDate.value.getFullYear(), viewDate.value.getMonth() + 1, 1)
}
function setMonth(event) {
  viewDate.value = new Date(viewDate.value.getFullYear(), Number(event.target.value), 1)
}
function setYear(event) {
  viewDate.value = new Date(Number(event.target.value), viewDate.value.getMonth(), 1)
}
function clear() {
  emit('update:modelValue', '')
  open.value = false
}
function toggle() {
  open.value = !open.value
}

function onDocMousedown(event) {
  if (rootEl.value && !rootEl.value.contains(event.target)) open.value = false
}
watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('mousedown', onDocMousedown)
  else document.removeEventListener('mousedown', onDocMousedown)
})
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocMousedown))
</script>

<template>
  <div ref="rootEl" class="relative">
    <button type="button" class="vf-input flex items-center justify-between gap-2 text-left" @click="toggle">
      <span :class="displayText ? 'text-slate-800' : 'text-slate-400'">{{ displayText || 'gg.aa.yyyy' }}</span>
      <svg class="h-4 w-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
      </svg>
    </button>

    <div v-if="open" class="absolute z-30 mt-1 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
      <div class="mb-2 flex items-center justify-between gap-1">
        <button type="button" class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100" @click="prevMonth">‹</button>
        <div class="flex min-w-0 flex-1 items-center gap-1">
          <select
            class="min-w-0 flex-1 cursor-pointer rounded-lg border-0 bg-slate-50 py-1 text-center text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-400"
            :value="viewDate.getMonth()"
            @change="setMonth"
          >
            <option v-for="(m, idx) in MONTHS_TR" :key="m" :value="idx">{{ m }}</option>
          </select>
          <select
            class="w-[4.5rem] shrink-0 cursor-pointer rounded-lg border-0 bg-slate-50 py-1 text-center text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-400"
            :value="viewDate.getFullYear()"
            @change="setYear"
          >
            <option v-for="y in YEARS" :key="y" :value="y">{{ y }}</option>
          </select>
        </div>
        <button type="button" class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100" @click="nextMonth">›</button>
      </div>
      <div class="grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-400">
        <span v-for="d in DAYS_TR" :key="d">{{ d }}</span>
      </div>
      <div class="mt-1 grid grid-cols-7 gap-1">
        <button
          v-for="(day, idx) in calendarDays"
          :key="idx"
          type="button"
          class="h-8 rounded-lg text-sm"
          :class="!day ? 'invisible' : isSameDay(day, selected) ? 'bg-brand-600 font-bold text-white' : 'text-slate-700 hover:bg-slate-100'"
          @click="pick(day)"
        >
          {{ day ? day.getDate() : '' }}
        </button>
      </div>
      <button v-if="modelValue" type="button" class="mt-2 w-full rounded-lg py-1 text-center text-xs font-semibold text-slate-400 hover:bg-slate-50 hover:text-slate-600" @click="clear">
        Temizle
      </button>
    </div>
  </div>
</template>
