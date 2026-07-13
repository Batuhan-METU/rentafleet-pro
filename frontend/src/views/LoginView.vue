<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/authStore.js'
import { useBrandingStore } from '../stores/brandingStore.js'
import { setCompanySlug } from '../utils/company.js'

const auth = useAuthStore()
const branding = useBrandingStore()
const username = ref('')
const password = ref('')

const demoAccounts = [
  { label: 'Ahmet Rent A Car', user: 'ahmet_mudur', pass: 'ahmet123', company: 'ahmet' },
  { label: 'Ercan Rent A Car', user: 'ercan_mudur', pass: 'ercan123', company: 'ercan' },
]

const trustItems = ['Canlı Takip', 'AI Analiz', 'Piyasa Fiyatı', 'White-Label', 'Şirket İzolasyonu']

async function submit() {
  if (!username.value.trim() || !password.value) return
  await auth.login(username.value.trim(), password.value)
}

async function loginAsDemo(account) {
  setCompanySlug(account.company)
  username.value = account.user
  password.value = account.pass
  await branding.fetchBranding()
  await auth.login(account.user, account.pass)
}
</script>

<template>
  <div class="rf-ambient grid min-h-screen lg:grid-cols-2">
    <!-- Sol: koyu hero panel (BandLab split) -->
    <div class="rf-login-hero">
      <div class="rf-login-burst" aria-hidden="true" />
      <div class="relative z-10 max-w-md">
        <img
          v-if="branding.logo_url"
          :src="branding.logo_url"
          :alt="branding.display_name"
          class="mb-6 h-16 w-16 rounded-2xl object-cover ring-2 ring-white/20"
        />
        <div
          v-else
          class="mb-6 grid h-16 w-16 place-items-center rounded-2xl text-xl font-black ring-2 ring-white/20"
          :style="{ background: `linear-gradient(135deg, ${branding.primary_color}, ${branding.secondary_color})` }"
        >
          {{ branding.logoInitials }}
        </div>
        <h1 class="text-4xl font-black leading-tight tracking-tight">
          {{ branding.display_name }}
        </h1>
        <p class="mt-4 text-base leading-relaxed text-white/70">
          Her filo için tasarlanmış akıllı yönetim platformu. Araçlarınızı izleyin, fiyatlayın ve kararlarınızı veriye dayandırın.
        </p>
        <div class="rf-trust-strip mt-10 !justify-start !bg-white/10 !border-white/15">
          <span v-for="item in trustItems" :key="item" class="rf-trust-item !text-white/50">
            {{ item }}
          </span>
        </div>
      </div>
    </div>

    <!-- Sağ: giriş formu -->
    <div class="flex flex-col items-center justify-center px-4 py-10 lg:px-12">
      <div class="w-full max-w-md lg:hidden mb-8 text-center">
        <h1 class="text-2xl font-black text-slate-900">{{ branding.display_name }}</h1>
        <p class="mt-1 text-sm text-slate-500/80">Kurumsal Filo Yönetim Paneli</p>
      </div>

      <form class="rf-glass-strong w-full max-w-md rounded-3xl p-8 shadow-2xl" @submit.prevent="submit">
        <h2 class="text-2xl font-black tracking-tight text-slate-900">Giriş Yap</h2>
        <p class="mt-1 text-sm text-slate-500/80">Demo için aşağıdaki butonlardan birine tıklayın.</p>

        <div class="mt-6 space-y-4">
          <div>
            <label for="username" class="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-500/75">Kullanıcı Adı</label>
            <input id="username" v-model="username" type="text" autocomplete="username" class="rf-input" placeholder="ahmet_mudur" />
          </div>
          <div>
            <label for="password" class="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-500/75">Şifre</label>
            <input id="password" v-model="password" type="password" autocomplete="current-password" class="rf-input" />
          </div>
        </div>

        <p v-if="auth.error" class="mt-4 rounded-2xl bg-red-500/10 px-3 py-2 text-sm font-medium text-red-600 ring-1 ring-red-300/30">
          {{ auth.error }}
        </p>

        <button type="submit" class="rf-btn-primary mt-6 w-full" :disabled="auth.loading">
          {{ auth.loading ? 'Giriş yapılıyor...' : 'Panele Gir' }}
        </button>

        <div class="mt-6 border-t border-white/30 pt-5">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Tek Tık Demo Giriş</p>
          <div class="mt-3 flex flex-col gap-2">
            <button
              v-for="demo in demoAccounts"
              :key="demo.user"
              type="button"
              class="rf-glass rounded-full px-4 py-3 text-sm font-semibold text-slate-700 transition-all duration-300 ease-in-out hover:-translate-y-0.5 hover:shadow-lg disabled:opacity-60"
              :disabled="auth.loading"
              @click="loginAsDemo(demo)"
            >
              {{ demo.label }}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
