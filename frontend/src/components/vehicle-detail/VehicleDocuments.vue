<script setup>
import { onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import { formatDate } from '../../utils/format.js'

const props = defineProps({
  vehicleId: { type: Number, required: true },
})

const finance = useFinanceStore()
const loading = ref(false)
const uploading = ref(false)
const errorMsg = ref('')
const docs = ref([])

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    docs.value = await finance.fetchDocuments(props.vehicleId)
  } catch {
    errorMsg.value = 'Dosyalar yüklenemedi.'
  } finally {
    loading.value = false
  }
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function onFilesSelected(event) {
  const files = Array.from(event.target.files ?? [])
  event.target.value = ''
  if (!files.length) return
  uploading.value = true
  errorMsg.value = ''
  try {
    for (const file of files) {
      await finance.uploadDocument(props.vehicleId, file)
    }
    docs.value = await finance.fetchDocuments(props.vehicleId)
  } catch {
    errorMsg.value = 'Bir veya birden fazla dosya yüklenemedi.'
  } finally {
    uploading.value = false
  }
}

async function remove(doc) {
  errorMsg.value = ''
  try {
    await finance.deleteDocument(props.vehicleId, doc.id)
    docs.value = docs.value.filter((d) => d.id !== doc.id)
  } catch {
    errorMsg.value = 'Dosya silinemedi.'
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h3 class="mb-4 text-xl font-black text-slate-900">Dosyalar ve Ekler</h3>

    <label
      class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/60 py-8 text-sm font-semibold text-slate-500 transition-colors hover:border-brand-400 hover:bg-brand-50/40 hover:text-brand-700"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l-3 3m3-3l3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
      </svg>
      {{ uploading ? 'Yükleniyor…' : 'Dosya seçmek için tıklayın' }}
      <input type="file" multiple class="hidden" :disabled="uploading" @change="onFilesSelected" />
    </label>

    <p v-if="errorMsg" class="mt-2 text-xs font-semibold text-rose-600">{{ errorMsg }}</p>

    <div v-if="loading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
    <p v-else-if="!docs.length" class="mt-4 text-sm text-slate-400">Henüz dosya eklenmemiş.</p>
    <ul v-else class="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
      <li v-for="doc in docs" :key="doc.id" class="flex items-center gap-3 px-4 py-3">
        <a :href="doc.file" target="_blank" rel="noopener" class="min-w-0 flex-1 truncate text-sm font-semibold text-brand-700 hover:underline">
          {{ doc.original_filename }}
        </a>
        <span v-if="doc.label" class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">{{ doc.label }}</span>
        <span class="shrink-0 text-xs text-slate-400">{{ formatSize(doc.size) }}</span>
        <span class="shrink-0 text-xs text-slate-400">{{ formatDate(doc.uploaded_at) }}</span>
        <button type="button" class="shrink-0 text-slate-400 hover:text-rose-600" @click="remove(doc)">✕</button>
      </li>
    </ul>
  </div>
</template>
