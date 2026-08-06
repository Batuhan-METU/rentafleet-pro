// Araç detay sayfası sekmeleri — sıra, kullanıcının paylaştığı FYS ekran
// görüntüsündeki sırayla birebir eşleşir. `ready: false` olanlar için henüz
// backend modeli yok, sekme "Yakında" placeholder'ı render eder.
export const VEHICLE_DETAIL_TABS = [
  { id: 'overview', label: 'Araç Detayı', ready: true },
  { id: 'financing', label: 'Finansman', ready: true },
  { id: 'insurance-policies', label: 'Poliçeler', ready: true },
  { id: 'rentals', label: 'Aracın Kira/Rezervasyonları', ready: true },
  { id: 'traffic-fines', label: 'Trafik Ceza Listesi', ready: false },
  { id: 'inspection', label: 'Muayene', ready: false },
  { id: 'fuel-usage', label: 'Yakıt Kullanımı', ready: false },
  { id: 'equipment', label: 'Ekipman', ready: false },
  { id: 'damage', label: 'Hasar Detayı', ready: false },
  { id: 'service-history', label: 'Eski Servis Kayıtları', ready: false },
  { id: 'tire-group', label: 'Lastik Grup Tanımlama', ready: false },
  { id: 'files', label: 'Dosyalar', ready: true },
]
