// Uygulamanın tüm localStorage anahtarları TEK burada tanımlanır. Önceden
// altı farklı dosyada (authStore, utils/company, rentalWorkflowStore,
// vehicleStore, LoanDataTable, services/api+aiConsultStream) bağımsız
// `rf_*` literal'leri vardı — `services/api.js` ve `services/aiConsultStream.js`
// hatta authStore'un TOKEN_KEY'ini import ETMEDEN kendi 'rf_token' kopyalarını
// tutuyordu, yani authStore'daki değer değişse ikisi sessizce senkronsuz
// kalırdı. Yeni bir anahtar eklerken/mevcut birini değiştirirken artık tek
// yer var.
export const TOKEN_KEY = 'rf_token'
export const USER_KEY = 'rf_user'
export const COMPANY_SLUG_KEY = 'rf_company_slug'
export const RENTAL_WORKFLOW_KEY = 'rf_rental_workflow'
export const MARKET_CACHE_PREFIX = 'rf_market_v2_'
export const LOAN_TABLE_COLUMNS_PREFIX = 'rf_loan_table_columns_'
export const LOAN_TABLE_TEMPLATES_PREFIX = 'rf_loan_table_templates_'
