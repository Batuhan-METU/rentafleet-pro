<script setup>
// Projede hiç aranabilir dropdown bileşeni yoktu (bkz. plan) — sıfırdan
// yazılmış, hafif bir tip-yaz-filtrele seçici. "İçerir" eşleşmesi kullanır
// (Araçlar listesindeki prefix aramadan farklı, standart dropdown-arama
// davranışı). Harici bağımlılık eklemez, projenin sıfır-bağımlılık
// stiliyle tutarlıdır.
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, required: true }, // [{ value, label }]
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const query = ref('')
const highlighted = ref(-1)
const rootEl = ref(null)

const selectedLabel = computed(
  () => props.options.find((o) => o.value === props.modelValue)?.label ?? '',
)

watch(
  () => props.modelValue,
  () => {
    if (!open.value) query.value = ''
  },
)

const filtered = computed(() => {
  const q = query.value.trim().toLocaleLowerCase('tr')
  if (!q) return props.options
  return props.options.filter((o) => o.label.toLocaleLowerCase('tr').includes(q))
})

function openList() {
  if (props.disabled) return
  open.value = true
  query.value = ''
  highlighted.value = filtered.value.findIndex((o) => o.value === props.modelValue)
}

function pick(option) {
  emit('update:modelValue', option.value)
  open.value = false
  query.value = ''
}

function clearSelection() {
  emit('update:modelValue', '')
  query.value = ''
}

function onKeydown(event) {
  if (!open.value) {
    if (event.key === 'ArrowDown' || event.key === 'Enter') {
      event.preventDefault()
      openList()
    }
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    highlighted.value = Math.min(highlighted.value + 1, filtered.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlighted.value = Math.max(highlighted.value - 1, 0)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const opt = filtered.value[highlighted.value]
    if (opt) pick(opt)
  } else if (event.key === 'Escape') {
    open.value = false
  }
}

function onBlur() {
  // Liste içindeki bir tıklamaya izin vermek için kapatmayı bir tık geciktir.
  nextTick(() => setTimeout(() => { open.value = false }, 120))
}
</script>

<template>
  <div ref="rootEl" class="relative">
    <div class="relative">
      <input
        class="vf-input pr-8"
        :value="open ? query : selectedLabel"
        :placeholder="placeholder"
        :disabled="disabled"
        role="combobox"
        aria-expanded="open"
        @focus="openList"
        @input="query = $event.target.value; open = true"
        @keydown="onKeydown"
        @blur="onBlur"
      />
      <button
        v-if="modelValue && !open"
        type="button"
        class="absolute right-7 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
        tabindex="-1"
        @mousedown.prevent="clearSelection"
      >
        ✕
      </button>
      <!-- Bu alanın seçmeli (dropdown) olduğunu belirten ok işareti — açıkken
           yukarı, kapalıyken aşağı bakar. -->
      <svg
        class="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 transition-transform"
        :class="{ 'rotate-180': open }"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
    <ul
      v-if="open"
      role="listbox"
      class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
    >
      <li v-if="!filtered.length" class="px-3 py-2 text-sm text-slate-400">Sonuç yok</li>
      <li
        v-for="(option, idx) in filtered"
        :key="option.value"
        role="option"
        class="cursor-pointer px-3 py-1.5 text-sm"
        :class="idx === highlighted ? 'bg-brand-50 text-brand-700' : 'text-slate-700 hover:bg-slate-50'"
        @mousedown.prevent="pick(option)"
        @mouseenter="highlighted = idx"
      >
        {{ option.label }}
      </li>
    </ul>
  </div>
</template>
