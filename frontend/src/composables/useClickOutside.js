import { onBeforeUnmount, onMounted } from 'vue'

/**
 * `elRef`'in İÇİNDE olmayan bir yere mousedown yapılınca `onOutsideClick`
 * çağrılır — `NotificationBell.vue` ve `LoanDataTable.vue`'de birebir aynı
 * şekilde tekrarlanıyordu. `DatePicker.vue`'deki daha ince ayarlı sürüm
 * (dinleyiciyi yalnızca panel açıkken ekleyip kaldıran) kasıtlı olarak
 * buraya taşınmadı — farklı bir optimizasyon şekli, davranışını
 * değiştirmemek için olduğu gibi bırakıldı.
 */
export function useClickOutside(elRef, onOutsideClick) {
  function handleMousedown(event) {
    if (elRef.value && !elRef.value.contains(event.target)) onOutsideClick(event)
  }

  onMounted(() => document.addEventListener('mousedown', handleMousedown))
  onBeforeUnmount(() => document.removeEventListener('mousedown', handleMousedown))
}
