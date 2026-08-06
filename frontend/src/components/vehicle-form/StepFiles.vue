<script setup>
// Yeni araç ekleme sırasında araç henüz bir ID'ye sahip değil — bu yüzden
// seçilen dosyalar burada SADECE bellekte bekletilir (form.stagedFiles),
// gerçek yükleme VehicleWizardForm.vue'nun submit()'inde araç
// oluşturulduktan HEMEN SONRA yapılır. Düzenleme modunda (form.id dolu)
// ise dosya seçilir seçilmez anında yüklenir/silinir — beklemeye gerek yok.
import { markRaw, onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'

const props = defineProps({
  form: { type: Object, required: true },
})

const finance = useFinanceStore()
const uploading = ref(false)
const errorMsg = ref('')

const isEdit = !!props.form.id
const existingDocs = ref([])

onMounted(async () => {
  if (isEdit) {
    try {
      existingDocs.value = await finance.fetchDocuments(props.form.id)
    } catch {
      errorMsg.value = 'Mevcut dosyalar yüklenemedi.'
    }
  }
})

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

  if (isEdit) {
    uploading.value = true
    errorMsg.value = ''
    try {
      for (const file of files) {
        await finance.uploadDocument(props.form.id, file)
      }
      existingDocs.value = await finance.fetchDocuments(props.form.id)
    } catch {
      errorMsg.value = 'Bir veya birden fazla dosya yüklenemedi.'
    } finally {
      uploading.value = false
    }
  } else {
    for (const file of files) {
      props.form.stagedFiles.push({ file: markRaw(file), label: '' })
    }
  }
}

function removeStaged(idx) {
  props.form.stagedFiles.splice(idx, 1)
}

async function removeExisting(doc) {
  errorMsg.value = ''
  try {
    await finance.deleteDocument(props.form.id, doc.id)
    existingDocs.value = existingDocs.value.filter((d) => d.id !== doc.id)
  } catch {
    errorMsg.value = 'Dosya silinemedi.'
  }
}
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Dosyalar ve Ekler</h3>
    <p class="mb-4 text-xs text-slate-500">
      Ruhsat fotokopisi, poliçe PDF'i, ekspertiz raporu gibi araca ait serbest dosyalar.
    </p>

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

    <!-- Yeni araç: yükleme aracın kaydından sonra yapılacak, bekleyen liste -->
    <ul v-if="!isEdit && form.stagedFiles.length" class="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-100">
      <li v-for="(item, idx) in form.stagedFiles" :key="idx" class="flex items-center gap-3 px-3 py-2.5">
        <span class="min-w-0 flex-1 truncate text-sm text-slate-700">{{ item.file.name }}</span>
        <span class="shrink-0 text-xs text-slate-400">{{ formatSize(item.file.size) }}</span>
        <button type="button" class="shrink-0 text-slate-400 hover:text-rose-600" @click="removeStaged(idx)">✕</button>
      </li>
    </ul>
    <p v-else-if="!isEdit" class="mt-3 text-xs text-slate-400">
      Henüz dosya seçilmedi — aracı kaydettiğinizde seçtiğiniz dosyalar otomatik yüklenir.
    </p>

    <!-- Düzenleme: mevcut dosyalar, anında yüklenir/silinir -->
    <ul v-if="isEdit && existingDocs.length" class="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-100">
      <li v-for="doc in existingDocs" :key="doc.id" class="flex items-center gap-3 px-3 py-2.5">
        <a :href="doc.file" target="_blank" rel="noopener" class="min-w-0 flex-1 truncate text-sm text-brand-700 hover:underline">
          {{ doc.original_filename }}
        </a>
        <span class="shrink-0 text-xs text-slate-400">{{ formatSize(doc.size) }}</span>
        <button type="button" class="shrink-0 text-slate-400 hover:text-rose-600" @click="removeExisting(doc)">✕</button>
      </li>
    </ul>
  </section>
</template>
