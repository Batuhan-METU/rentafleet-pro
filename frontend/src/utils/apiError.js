// DRF hata yanıtları (`{ error: "..." }`) tüm formlarda/modallerde aynı
// şekilde `err?.response?.data?.error ?? 'fallback metni'` ile okunuyordu —
// tek satırlık bir ifade olsa da 9 dosyada tekrarlanıyordu. Değişiklik
// gerektiğinde (ör. backend hata şeklini genişletirse) hepsini tek tek
// bulmak yerine buradan yönetilsin diye.
export function getApiErrorMessage(err, fallback) {
  return err?.response?.data?.error ?? fallback
}
