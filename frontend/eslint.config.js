import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  // Formatlama tamamen Prettier'a bırakılır (`npm run format`) — ESLint
  // burada yalnızca kod KALİTESİ kurallarını denetler; ikisini karıştırmak
  // (eslint-plugin-prettier) 900+ salt boşluk/tırnak uyarısıyla gerçek
  // hataları gömerdi.
  skipFormatting,
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      // Bileşenlerin çoğu tek dosyalık, tek kullanımlık ekranlar
      // (VehicleDetailOverview, Workspace) — çok-kelimeli isim zorunluluğu
      // buradaki mevcut adlandırma kuralına uymuyor.
      'vue/multi-word-component-names': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      // Sihirbaz adımları (driver-form/vehicle-form/Step*.vue) kasıtlı
      // olarak TEK paylaşılan reaktif `form` nesnesini prop olarak alıp
      // alanlarını doğrudan mutasyona uğratır — her alan için ayrı
      // update:xxx event'i yaymak yerine. Vue 3'te bu güvenlidir (nesne
      // referansı aynı kalır, reaktivite parent'a doğru akar); kural
      // bunu genel olarak yasakladığı için burada kapatılır.
      'vue/no-mutating-props': 'off',
    },
  },
  {
    files: ['**/*.test.js'],
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },
  },
]
