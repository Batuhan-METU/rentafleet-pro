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
      <section class="rf-glass-strong rounded-3xl p-6">
        <h2 class="text-lg font-black tracking-tight text-slate-900">Şirket &amp; Marka</h2>
        <p class="mt-1 text-sm text-slate-500">
          Genel bakış sayfası ve panel görünümü bu bilgilere göre güncellenir.
        </p>

        <div class="mt-5 grid gap-6 lg:grid-cols-[1fr_auto]">
          <div class="grid gap-4 md:grid-cols-2">
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Ticari unvan</span>
              <input v-model="form.display_name" class="rf-input" placeholder="Ercan Filo" />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Şirket açıklaması</span>
              <textarea
                v-model="form.description"
                rows="4"
                class="rf-input resize-none"
                placeholder="Şirketinizi müşterilere ve ekibinize tanıtan kısa bir metin…"
              />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Yasal unvan (salt okunur)</span>
              <input :value="company.name" class="rf-input !bg-slate-100/60" disabled />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Vergi numarası (salt okunur)</span>
              <input :value="company.tax_number" class="rf-input !bg-slate-100/60" disabled />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Logo URL</span>
              <input v-model="form.logo_url" class="rf-input" placeholder="https://…" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Ana renk</span>
              <div class="flex gap-2">
                <input v-model="form.primary_color" type="color" class="h-10 w-12 cursor-pointer rounded-xl border border-white/50" />
                <input v-model="form.primary_color" class="rf-input flex-1 font-mono text-sm" />
              </div>
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-bold uppercase tracking-wide text-slate-500">Menü rengi</span>
              <div class="flex gap-2">
                <input v-model="form.secondary_color" type="color" class="h-10 w-12 cursor-pointer rounded-xl border border-white/50" />
                <input v-model="form.secondary_color" class="rf-input flex-1 font-mono text-sm" />
              </div>
            </label>
          </div>

          <!-- Canlı marka önizlemesi: kaydetmeden nasıl görüneceğini gösterir -->
          <div class="w-full lg:w-48">
            <p class="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">Önizleme</p>
            <div
              class="overflow-hidden rounded-2xl shadow-lg ring-1 ring-black/5"
              :style="{ background: `linear-gradient(160deg, ${form.secondary_color}, ${form.primary_color})` }"
            >
              <div class="p-4">
                <div
                  class="grid h-9 w-9 place-items-center rounded-xl text-xs font-black text-white ring-2 ring-white/30"
                  :style="{ background: `linear-gradient(135deg, ${form.primary_color}, ${form.secondary_color})` }"
                >
                  {{ (form.display_name || 'RP').slice(0, 2).toUpperCase() }}
                </div>
                <p class="mt-3 truncate text-sm font-black text-white">{{ form.display_name || 'Şirket Adı' }}</p>
                <p class="text-[11px] text-white/60">Filo Yönetimi</p>
              </div>
              <div class="space-y-1.5 bg-black/10 p-3">
                <div class="h-2 w-4/5 rounded-full bg-white/25"></div>
                <div class="h-2 w-3/5 rounded-full bg-white/15"></div>
                <div class="h-2 w-2/3 rounded-full bg-white/15"></div>
              </div>
            </div>
            <p class="mt-2 text-center text-[11px] text-slate-400">Kenar menüsü önizlemesi</p>
          </div>
        </div>

        <p v-if="store.saveError" class="mt-4 text-sm font-semibold text-red-600">{{ store.saveError }}</p>

        <div class="mt-5 flex justify-end">
          <button
            type="button"
            class="rf-btn-primary disabled:opacity-50"
            :disabled="store.saving"
            @click="saveCompany"
          >
            {{ store.saving ? 'Kaydediliyor…' : 'Kaydet' }}
          </button>
        </div>
      </section>

      <!-- Personel -->
      <section class="rf-glass-strong rounded-3xl p-6">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="text-lg font-black tracking-tight text-slate-900">Personel</h2>
            <p class="mt-1 text-sm text-slate-500">Operasyon personeli ekleyin; araç ve sürücü ekranlarına erişirler.</p>
          </div>
          <button
            type="button"
            class="rf-btn-ghost"
            @click="showPersonnelForm = !showPersonnelForm"
          >
            {{ showPersonnelForm ? 'İptal' : 'Personel Ekle' }}
          </button>
        </div>

        <form
          v-if="showPersonnelForm"
          class="mt-4 grid gap-3 rounded-2xl bg-slate-900/[0.03] p-4 md:grid-cols-2"
          @submit.prevent="submitPersonnel"
        >
          <input v-model="personnelForm.username" class="rf-input" placeholder="Kullanıcı adı *" required />
          <input v-model="personnelForm.password" type="password" class="rf-input" placeholder="Şifre *" required />
          <input v-model="personnelForm.first_name" class="rf-input" placeholder="Ad" />
          <input v-model="personnelForm.last_name" class="rf-input" placeholder="Soyad" />
          <input v-model="personnelForm.email" type="email" class="rf-input md:col-span-2" placeholder="E-posta" />
          <div class="md:col-span-2 flex justify-end">
            <button
              type="submit"
              class="rf-btn-primary disabled:opacity-50"
              :disabled="addingPersonnel"
            >
              {{ addingPersonnel ? 'Ekleniyor…' : 'Ekle' }}
            </button>
          </div>
        </form>

        <p v-if="store.personnelError" class="mt-3 text-sm font-semibold text-red-600">{{ store.personnelError }}</p>

        <div v-if="store.personnelLoading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
        <div v-else-if="store.personnel.length" class="mt-4 overflow-hidden rounded-2xl ring-1 ring-white/40">
          <table class="w-full text-left text-sm">
            <thead class="bg-slate-900/[0.03] text-xs font-bold uppercase tracking-wide text-slate-500">
              <tr>
                <th class="px-4 py-3">Ad Soyad</th>
                <th class="px-4 py-3">Kullanıcı adı</th>
                <th class="px-4 py-3">Rol</th>
                <th class="px-4 py-3">E-posta</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-white/40">
              <tr v-for="p in store.personnel" :key="p.id" class="transition-colors hover:bg-white/40">
                <td class="px-4 py-3 font-bold text-slate-900">{{ p.full_name }}</td>
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
      <section class="rf-glass-strong rounded-3xl p-6">
        <h2 class="text-lg font-black tracking-tight text-slate-900">Hesabım</h2>
        <dl class="mt-4 grid gap-3 sm:grid-cols-2">
          <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Ad Soyad</dt>
            <dd class="font-bold text-slate-900">{{ auth.displayName }}</dd>
          </div>
          <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Rol</dt>
            <dd class="font-bold text-slate-900">{{ auth.roleLabel }}</dd>
          </div>
          <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Kullanıcı adı</dt>
            <dd class="font-bold text-slate-900">{{ auth.user?.username }}</dd>
          </div>
          <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Şirket kaydı</dt>
            <dd class="font-bold text-slate-900">{{ formatDate(company.created_at) }}</dd>
          </div>
        </dl>
      </section>

      <!-- Sistem -->
      <section class="rf-glass-strong rounded-3xl p-6">
        <h2 class="text-lg font-black tracking-tight text-slate-900">Sistem</h2>
        <p class="mt-1 text-sm text-slate-500">Telemetri ve canlı takip arka planda bu servislere bağlanır.</p>
        <dl class="mt-4 grid gap-3 sm:grid-cols-3">
          <div class="rounded-2xl bg-emerald-50 px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-emerald-700/70">Veritabanı</dt>
            <dd class="font-bold text-emerald-700">{{ store.systemStatus?.relational === 'ok' ? 'Çalışıyor' : '—' }}</dd>
          </div>
          <div class="rounded-2xl px-4 py-3" :class="store.systemStatus?.clickhouse === 'ok' ? 'bg-emerald-50' : 'bg-amber-50'">
            <dt class="text-[10px] font-bold uppercase tracking-wide" :class="store.systemStatus?.clickhouse === 'ok' ? 'text-emerald-700/70' : 'text-amber-700/70'">Telemetri deposu</dt>
            <dd
              class="font-bold"
              :class="store.systemStatus?.clickhouse === 'ok' ? 'text-emerald-700' : 'text-amber-700'"
            >
              {{ chStatusLabel }}
            </dd>
          </div>
          <div class="rounded-2xl bg-slate-900/[0.03] px-4 py-3">
            <dt class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Filo</dt>
            <dd class="font-bold text-slate-900">{{ company.vehicle_count ?? 0 }} araç</dd>
          </div>
        </dl>
      </section>
    </template>
  </div>
</template>
