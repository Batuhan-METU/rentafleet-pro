<script setup>
// Sürücü ekleme modalı — Araç Ekle ile AYNI kabuk deseni (VehicleFormModal.vue).
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useModalLifecycle } from '../composables/useModalLifecycle.js'
import DriverWizardForm from './driver-form/DriverWizardForm.vue'

const emit = defineEmits(['close', 'saved'])

const workflow = useRentalWorkflowStore()

useModalLifecycle(() => emit('close'))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div class="absolute inset-0 bg-slate-900/50" aria-hidden="true" @click="emit('close')" />

      <div
        class="relative z-10 flex h-[min(92vh,100dvh-2rem)] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <header class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div class="min-w-0">
            <h2 class="text-lg font-semibold leading-tight text-slate-900">Yeni Sürücü Ekle</h2>
            <p class="mt-1 text-sm leading-snug text-slate-500">
              Kayıt sonrası risk skoru ve uygun araçlar otomatik hesaplanır.
            </p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Kapat"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex min-h-0 flex-1 flex-col px-6 py-5">
          <div v-if="workflow.active" class="mb-4 shrink-0 rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800">
            <strong>Adım 2 — Sürücü bilgileri.</strong> Müşteri fiyatı kabul etti; bilgilerini girin.
            <span v-if="workflow.vehicleLabel" class="mt-1 block text-xs">Araç: {{ workflow.vehicleLabel }}</span>
          </div>

          <DriverWizardForm @saved="(d) => emit('saved', d)" @cancel="emit('close')" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
