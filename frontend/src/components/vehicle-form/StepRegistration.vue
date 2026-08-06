<script setup>
import DatePicker from './DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
  isEdit: { type: Boolean, default: false },
})
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-900">Ruhsat Bilgileri</h3>
      <p class="mb-4 text-xs text-slate-500">
        Resmi ruhsat belgesindeki alanlar — parantez içindeki harf/numaralar
        belgedeki karşılığıdır. Plaka/Marka/Ticari Adı/Model Yılı/Rengi/Şasi
        Numarası, "Araç Bilgileri" adımıyla AYNI alanlardır.
      </p>

      <h4 class="mb-2 mt-1 text-sm font-bold uppercase tracking-wide text-slate-800">Tescil Bilgileri</h4>
      <div class="mb-5 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Ruhsat Seri No</span>
          <input v-model="form.registration.registration_serial_no" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Y.1) İl</span>
          <input v-model="form.registration.registration_province" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Y.1) İlçe</span>
          <input v-model="form.registration.registration_district" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(A) Plaka *</span>
          <input v-model="form.plate_number" class="vf-input" :disabled="isEdit" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(B) İlk Tescil Tarihi</span>
          <DatePicker v-model="form.registration.first_registration_date" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Y.2) Tescil Sıra No</span>
          <input v-model="form.registration.registration_sequence_no" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(I) Tescil Tarihi</span>
          <DatePicker v-model="form.registration.registration_date" />
        </label>
      </div>

      <h4 class="mb-2 mt-1 text-sm font-bold uppercase tracking-wide text-slate-800">Araç Kimliği</h4>
      <div class="mb-5 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(D.1) Marka *</span>
          <input v-model="form.brand" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(D.2) Tipi</span>
          <input v-model="form.registration.vehicle_type_code" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(D.3) Ticari Adı *</span>
          <input v-model="form.model" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Donanım Paketi</span>
          <input v-model="form.package" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(D.4) Model Yılı</span>
          <input v-model="form.production_year" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(J) Araç Sınıfı</span>
          <input v-model="form.registration.vehicle_class" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(D.5) Cinsi</span>
          <input v-model="form.registration.vehicle_kind" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(R) Rengi</span>
          <input v-model="form.color" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(P.5) Motor No</span>
          <input v-model="form.registration.engine_serial_number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(E) Şasi Numarası *</span>
          <input v-model="form.plate_chassis" class="vf-input" />
        </label>
      </div>

      <h4 class="mb-2 mt-1 text-sm font-bold uppercase tracking-wide text-slate-800">Ağırlık, Kapasite ve Motor</h4>
      <div class="mb-5 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(G.1) Net Ağırlığı (Kg)</span>
          <input v-model="form.registration.net_weight_kg" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(F.1) Azami Yüklü Ağırlığı (Kg)</span>
          <input v-model="form.registration.max_loaded_weight_kg" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(G) Katar Ağırlığı (Kg)</span>
          <input v-model="form.registration.train_weight_kg" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(G.2) Römork Azami Yüklü Ağırlığı (Kg)</span>
          <input v-model="form.registration.trailer_max_weight_kg" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(S.1) Koltuk Sayısı (Sür. Dahil)</span>
          <input v-model="form.registration.seat_count" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(S.2) Ayakta Yolcu Sayısı</span>
          <input v-model="form.registration.standing_passenger_count" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(P.1) Silindir Hacmi (cm³)</span>
          <input v-model="form.engine_displacement_cc" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(P.2) Motor Gücü (hp)</span>
          <input v-model="form.engine_power_hp" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Q) Güç Ağırlık Oranı (kw/kg)</span>
          <input v-model="form.registration.power_to_weight_ratio" type="number" step="0.001" class="vf-input" />
        </label>
      </div>

      <h4 class="mb-2 mt-1 text-sm font-bold uppercase tracking-wide text-slate-800">Kullanım, Onay ve Sahiplik</h4>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Y.3) Kullanım Amacı</span>
          <input v-model="form.registration.usage_purpose" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(K) Tip Onay No</span>
          <input v-model="form.registration.type_approval_no" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Y.4) TC No/Vergi No</span>
          <input v-model="form.registration.owner_tc_or_tax_no" class="vf-input" maxlength="16" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(C.1.1) Soyadı/Ticari Ünvanı</span>
          <input v-model="form.registration.owner_surname_or_title" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">(C.1.2) Adı</span>
          <input v-model="form.registration.owner_first_name" class="vf-input" />
        </label>
        <label class="block lg:col-span-2">
          <span class="mb-1 block text-xs font-medium text-slate-500">(C.1.3) Adres</span>
          <input v-model="form.registration.owner_address" class="vf-input" />
        </label>
        <label class="block lg:col-span-2">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Z.1) Araç Üzerinde Hak ve Menfaati Bulunanlar</span>
          <input v-model="form.registration.rights_holders_note" class="vf-input" />
        </label>
        <label class="block lg:col-span-4">
          <span class="mb-1 block text-xs font-medium text-slate-500">(Z.2) Diğer Bilgiler</span>
          <textarea v-model="form.registration.other_notes" rows="2" class="vf-input resize-none" />
        </label>
      </div>
    </section>
  </div>
</template>
