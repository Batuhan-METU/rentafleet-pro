import { onBeforeUnmount, onMounted } from 'vue'

/**
 * Modal bileşenlerinin ortak açılış/kapanış davranışı — Escape tuşuna
 * basınca `onClose` çağrılır, modal açıkken arka plan kaydırılamaz (body
 * scroll lock). Bu üç satır 7 farklı modal bileşeninde birebir aynı şekilde
 * tekrarlanıyordu; bir bileşenin kendi ek `onMounted`/`onBeforeUnmount`
 * mantığı varsa (ör. bir önizleme çekmek, bir zamanlayıcı temizlemek) o
 * ayrı tutulur — Vue aynı setup içinde birden fazla `onMounted` kaydına
 * izin verir, ikisi de sırayla çalışır.
 */
export function useModalLifecycle(onClose) {
  function handleKeydown(event) {
    if (event.key === 'Escape') onClose()
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
    document.body.style.overflow = 'hidden'
  })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown)
    document.body.style.overflow = ''
  })
}
