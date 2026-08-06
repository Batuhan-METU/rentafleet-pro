// Fiyatlandırma ekranının varsayılan kiralama penceresi: yarından başlayıp
// 3 gün süren aralık. Hem PricingManager.vue'nun tarih alanlarını
// doldurmak hem de giriş sonrası arka plan ön-yüklemesinin (vehicleStore
// prefetchDefaultMarketWindow) AYNI tarihleri hedeflemesi için TEK
// kaynaktan üretilir — ikisi ayrı hesaplarsa önbellek anahtarları
// (marketSlotKey) uyuşmaz ve ön-yükleme boşa gider.
function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function getDefaultRentalWindow() {
  return {
    pickupDate: addDays(new Date(), 1),
    dropoffDate: addDays(new Date(), 4),
  }
}
