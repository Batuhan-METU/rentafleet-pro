/** Kiracı slug — localStorage + host subdomain. */
export const TENANT_SLUG_KEY = 'rf_tenant_slug'

export function inferTenantSlug(username = '') {
  return String(username).trim().toLowerCase().split('_')[0] || null
}

export function getTenantSlug() {
  return localStorage.getItem(TENANT_SLUG_KEY)
}

export function setTenantSlug(slug) {
  if (slug) localStorage.setItem(TENANT_SLUG_KEY, slug)
  else localStorage.removeItem(TENANT_SLUG_KEY)
}

export function syncTenantSlugFromHost() {
  const host = window.location.hostname.toLowerCase()
  if (host.endsWith('.localhost')) {
    const slug = host.split('.')[0]
    if (slug && slug !== 'www') {
      setTenantSlug(slug)
      return slug
    }
  }
  return getTenantSlug()
}
