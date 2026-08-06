import apiClient from '../services/api.js'

function localDateStamp() {
  const d = new Date()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

/**
 * Backend'deki bir Excel export endpoint'inden .xlsx indirir ve tarayıcıda
 * `<filenamePrefix>_<YYYY-AA-GG>.xlsx` adıyla kaydettirir.
 *
 * Ekrandaki filtreler `params` ile backend'e aynen iletilir; hata durumunda
 * çağıran bileşenin kendi mesajını gösterebilmesi için hata fırlatılır.
 *
 * @param {string} path - apiClient'a göre yol (ör. 'vehicles/export/').
 * @param {{ params?: Record<string, string>, filenamePrefix: string }} options
 */
export async function downloadExcelReport(path, { params = {}, filenamePrefix }) {
  const { data } = await apiClient.get(path, {
    params,
    responseType: 'blob',
    timeout: 60000,
  })

  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filenamePrefix}_${localDateStamp()}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
