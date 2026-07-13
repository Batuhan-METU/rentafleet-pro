/** Şirket slug — localStorage + host subdomain. */
export const COMPANY_SLUG_KEY = 'rf_company_slug'

export function inferCompanySlug(username = '') {
  return String(username).trim().toLowerCase().split('_')[0] || null
}

export function getCompanySlug() {
  return localStorage.getItem(COMPANY_SLUG_KEY)
}

export function setCompanySlug(slug) {
  if (slug) localStorage.setItem(COMPANY_SLUG_KEY, slug)
  else localStorage.removeItem(COMPANY_SLUG_KEY)
}

export function syncCompanySlugFromHost() {
  const host = window.location.hostname.toLowerCase()
  if (host.endsWith('.localhost')) {
    const slug = host.split('.')[0]
    if (slug && slug !== 'www') {
      setCompanySlug(slug)
      return slug
    }
  }
  return getCompanySlug()
}
