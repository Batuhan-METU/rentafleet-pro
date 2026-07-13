<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '../../stores/authStore.js'
import { useSettingsStore } from '../../stores/settingsStore.js'
import { formatDate } from '../../utils/format.js'

const auth = useAuthStore()
const store = useSettingsStore()

const form = reactive({
  display_name: '',
  description: '',
  logo_url: '',
  primary_color: '#3B82F6',
  secondary_color: '#1E3A8A',
})

const showPersonnelForm = ref(false)
const personnelForm = reactive({
  username: '',
  password: '',
  first_name: '',
  last_name: '',
  email: '',
})
const addingPersonnel = ref(false)

const company = computed(() => store.company)

onMounted(async () => {
  await Promise.all([store.fetchSettings(), store.fetchPersonnel(), store.fetchSystemStatus()])
  if (store.company) {
    form.display_name = store.company.display_name ?? ''
    form.description = store.company.description ?? ''
    form.logo_url = store.company.logo_url ?? ''
    form.primary_color = store.company.primary_color ?? '#3B82F6'
    form.secondary_color = store.company.secondary_color ?? '#1E3A8A'
  }
})

async function saveCompany() {
  try {
    await store.saveSettings({
      display_name: form.display_name.trim(),
      description: form.description.trim(),
      logo_url: form.logo_url.trim() || null,
      primary_color: form.primary_color,
      secondary_color: form.secondary_color,
    })
  } catch {
    // saveError store'da
  }
}

async function submitPersonnel() {
  if (!personnelForm.username.trim() || !personnelForm.password) {
    store.personnelError = 'Kullanıcı adı ve şifre zorunludur.'
    return
  }
  addingPersonnel.value = true
  try {
    await store.addPersonnel({
      username: personnelForm.username.trim(),
      password: personnelForm.password,
      first_name: personnelForm.first_name.trim(),
      last_name: personnelForm.last_name.trim(),
      email: personnelForm.email.trim(),
    })
    personnelForm.username = ''
    personnelForm.password = ''
    personnelForm.first_name = ''
    personnelForm.last_name = ''
    personnelForm.email = ''
    showPersonnelForm.value = false
  } catch {
    // personnelError store'da
  } finally {
    addingPersonnel.value = false
  }
}

const chStatusLabel = computed(() => {
  const s = store.systemStatus?.clickhouse
  if (s === 'ok') return 'Bağlı'
  if (s === 'unavailable') return 'Kapalı'
  return 'Bilinmiyor'
})
</script>

<template>
  <div class="space-y-8">
    <div v-if="store.loading && !company" class="grid place-items-center py-20">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
    </div>

    <div v-else-if="store.error" class="rounded-xl border border-red-200 bg-red-50 px-5 py-8 text-center text-red-700">
      Ayarlar yüklenemedi.
      <button type="button" class="ml-2 underline" @click="store.fetchSettings()">Tekrar dene</button>
    </div>

    <template v-else-if="company">
      <!-- Şirket & marka -->
      <section class="rounded-xl border border-slate-200 bg-white p-6">
        <h2 class="text-lg font-semibold text-slate-900">Şirket & Marka</h2>
        <p class="mt-1 text-sm text-slate-500">
          Genel bakış sayfası ve panel görünümü bu bilgilere göre güncellenir.
        </p>

        <div class="mt-5 grid gap-4 md:grid-cols-2">
          <label class="block md:col-span-2">
            <span class="mb-1 block text-xs font-medium text-slate-500">Ticari unvan</span>
            <input v-model="form.display_name" class="st-input" placeholder="Ercan Filo" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1 block text-xs font-medium text-slate-500">Şirket açıklaması</span>
            <textarea
              v-model="form.description"
              rows="4"
              class="st-input resize-none"
              placeholder="Şirketinizi müşterilere ve ekibinize tanıtan kısa bir metin…"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-500">Yasal unvan (salt okunur)</span>
            <input :value="company.name" class="st-input bg-slate-50" disabled />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-500">Vergi numarası (salt okunur)</span>
            <input :value="company.tax_number" class="st-input bg-slate-50" disabled />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1 block text-xs font-medium text-slate-500">Logo URL</span>
            <input v-model="form.logo_url" class="st-input" placeholder="https://…" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-500">Ana renk</span>
            <div class="flex gap-2">
              <input v-model="form.primary_color" type="color" class="h-10 w-12 cursor-pointer rounded border border-slate-200" />
              <input v-model="form.primary_color" class="st-input flex-1 font-mono text-sm" />
            </div>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-500">Menü rengi</span>
            <div class="flex gap-2">
              <input v-model="form.secondary_color" type="color" class="h-10 w-12 cursor-pointer rounded border border-slate-200" />
              <input v-model="form.secondary_color" class="st-input flex-1 font-mono text-sm" />
            </div>
          </label>
        </div>

        <p v-if="store.saveError" class="mt-4 text-sm text-red-600">{{ store.saveError }}</p>

        <div class="mt-5 flex justify-end">
          <button
            type="button"
            class="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            :disabled="store.saving"
            @click="saveCompany"
          >
            {{ store.saving ? 'Kaydediliyor…' : 'Kaydet' }}
          </button>
        </div>
      </section>

      <!-- Personel -->
      <section class="rounded-xl border border-slate-200 bg-white p-6">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">Personel</h2>
            <p class="mt-1 text-sm text-slate-500">Operasyon personeli ekleyin; araç ve sürücü ekranlarına erişirler.</p>
          </div>
          <button
            type="button"
            class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            @click="showPersonnelForm = !showPersonnelForm"
          >
            {{ showPersonnelForm ? 'İptal' : 'Personel Ekle' }}
          </button>
        </div>

        <form
          v-if="showPersonnelForm"
          class="mt-4 grid gap-3 rounded-lg border border-slate-100 bg-slate-50 p-4 md:grid-cols-2"
          @submit.prevent="submitPersonnel"
        >
          <input v-model="personnelForm.username" class="st-input" placeholder="Kullanıcı adı *" required />
          <input v-model="personnelForm.password" type="password" class="st-input" placeholder="Şifre *" required />
          <input v-model="personnelForm.first_name" class="st-input" placeholder="Ad" />
          <input v-model="personnelForm.last_name" class="st-input" placeholder="Soyad" />
          <input v-model="personnelForm.email" type="email" class="st-input md:col-span-2" placeholder="E-posta" />
          <div class="md:col-span-2 flex justify-end">
            <button
              type="submit"
              class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              :disabled="addingPersonnel"
            >
              {{ addingPersonnel ? 'Ekleniyor…' : 'Ekle' }}
            </button>
          </div>
        </form>

        <p v-if="store.personnelError" class="mt-3 text-sm text-red-600">{{ store.personnelError }}</p>

        <div v-if="store.personnelLoading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
        <div v-else-if="store.personnel.length" class="mt-4 overflow-hidden rounded-lg border border-slate-200">
          <table class="w-full text-left text-sm">
            <thead class="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th class="px-4 py-3">Ad Soyad</th>
                <th class="px-4 py-3">Kullanıcı adı</th>
                <th class="px-4 py-3">Rol</th>
                <th class="px-4 py-3">E-posta</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="p in store.personnel" :key="p.id">
                <td class="px-4 py-3 font-medium text-slate-900">{{ p.full_name }}</td>
                <td class="px-4 py-3 text-slate-600">{{ p.username }}</td>
                <td class="px-4 py-3 text-slate-600">{{ p.role_display }}</td>
                <td class="px-4 py-3 text-slate-500">{{ p.email || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="mt-4 text-sm text-slate-400">Henüz operasyon personeli yok.</p>
      </section>

      <!-- Hesabım -->
      <section class="rounded-xl border border-slate-200 bg-white p-6">
        <h2 class="text-lg font-semibold text-slate-900">Hesabım</h2>
        <dl class="mt-4 grid gap-3 sm:grid-cols-2">
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Ad Soyad</dt>
            <dd class="font-medium text-slate-900">{{ auth.displayName }}</dd>
          </div>
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Rol</dt>
            <dd class="font-medium text-slate-900">{{ auth.roleLabel }}</dd>
          </div>
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Kullanıcı adı</dt>
            <dd class="font-medium text-slate-900">{{ auth.user?.username }}</dd>
          </div>
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Şirket kaydı</dt>
            <dd class="font-medium text-slate-900">{{ formatDate(company.created_at) }}</dd>
          </div>
        </dl>
      </section>

      <!-- Sistem -->
      <section class="rounded-xl border border-slate-200 bg-white p-6">
        <h2 class="text-lg font-semibold text-slate-900">Sistem</h2>
        <p class="mt-1 text-sm text-slate-500">Telemetri ve canlı takip arka planda bu servislere bağlanır.</p>
        <dl class="mt-4 grid gap-3 sm:grid-cols-3">
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Veritabanı</dt>
            <dd class="font-medium text-emerald-700">{{ store.systemStatus?.relational === 'ok' ? 'Çalışıyor' : '—' }}</dd>
          </div>
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Telemetri deposu</dt>
            <dd
              class="font-medium"
              :class="store.systemStatus?.clickhouse === 'ok' ? 'text-emerald-700' : 'text-amber-700'"
            >
              {{ chStatusLabel }}
            </dd>
          </div>
          <div class="rounded-lg bg-slate-50 px-4 py-3">
            <dt class="text-xs text-slate-500">Filo</dt>
            <dd class="font-medium text-slate-900">{{ company.vehicle_count ?? 0 }} araç</dd>
          </div>
        </dl>
      </section>
    </template>
  </div>
</template>

<style scoped>
.st-input {
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 0.55rem 0.75rem;
  font-size: 0.875rem;
  color: #334155;
  outline: none;
}
.st-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px #dbeafe;
}
.st-input:disabled {
  color: #64748b;
  cursor: not-allowed;
}
</style>
