import './assets/app.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const app = createApp(App)

// Herhangi bir <ErrorBoundary> tarafından yakalanmayan (ör. bileşen ağacı
// dışında, bir event handler veya watcher içinde fırlayan) hatalar için son
// çare — en azından sessizce kaybolmasınlar, konsola düşsünler.
app.config.errorHandler = (err, instance, info) => {
  console.error('[app.config.errorHandler] Yakalanmamış hata:', err, info)
}

app.use(createPinia()).mount('#app')
