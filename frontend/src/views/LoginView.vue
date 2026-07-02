<script setup>
// Kurumsal giriş ekranı (Day 13 RBAC).
import { ref } from 'vue'
import { useAuthStore } from '../stores/authStore.js'

const auth = useAuthStore()
const username = ref('')
const password = ref('')

async function submit() {
  if (!username.value.trim() || !password.value) return
  await auth.login(username.value.trim(), password.value)
}

const demoAccounts = [
  { label: 'Filo Müdürü', user: 'mudur', pass: 'mudur123' },
  { label: 'Operasyon Personeli', user: 'operasyon', pass: 'operasyon123' },
]

function fillDemo(account) {
  username.value = account.user
  password.value = account.pass
}
</script>

<template>
  <div class="grid min-h-screen place-items-center bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 px-4">
    <div class="w-full max-w-md">
      <!-- Marka -->
      <div class="mb-8 text-center">
        <div class="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-600 text-xl font-extrabold text-white shadow-lg">
          RF
        </div>
        <h1 class="text-2xl font-bold text-white">RentA-Fleet <span class="font-normal text-slate-400">PRO</span></h1>
        <p class="mt-1 text-sm text-slate-400">Kurumsal Filo Yönetim Paneli</p>
      </div>

      <!-- Form -->
      <form
        class="rounded-2xl border border-white/10 bg-white p-8 shadow-2xl"
        @submit.prevent="submit"
      >
        <h2 class="text-lg font-bold text-slate-900">Giriş Yap</h2>
        <p class="mt-1 text-sm text-slate-500">Şirket personeli hesabınızla oturum açın.</p>

        <div class="mt-6 space-y-4">
          <div>
            <label for="username" class="mb-1.5 block text-sm font-medium text-slate-700">Kullanıcı Adı</label>
            <input
              id="username"
              v-model="username"
              type="text"
              autocomplete="username"
              class="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="mudur"
            />
          </div>
          <div>
            <label for="password" class="mb-1.5 block text-sm font-medium text-slate-700">Şifre</label>
            <input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="••••••••"
            />
          </div>
        </div>

        <p v-if="auth.error" class="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{{ auth.error }}</p>

        <button
          type="submit"
          class="mt-6 w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
          :disabled="auth.loading"
        >
          {{ auth.loading ? 'Giriş yapılıyor...' : 'Panele Gir' }}
        </button>

        <!-- Demo hesaplar -->
        <div class="mt-6 border-t border-slate-100 pt-5">
          <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Demo Hesaplar</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <button
              v-for="demo in demoAccounts"
              :key="demo.user"
              type="button"
              class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              @click="fillDemo(demo)"
            >
              {{ demo.label }}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
