const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, { method = 'GET', body, signal } = {}) {
  const options = {
    method,
    headers: {},
    signal,
  }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let message = `Ошибка ${response.status}`
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail.map((item) => item.msg).join(', ')
      }
    } catch {
      // Keep the HTTP status message.
    }
    throw new Error(message)
  }
  if (response.status === 204) return null
  return response.json()
}

export const api = {
  health: () => request('/api/health'),
  stores: () => request('/api/stores'),
  createStore: (payload) => request('/api/stores', { method: 'POST', body: payload }),
  store: (storeId) => request(`/api/stores/${storeId}`),
  updateStore: (storeId, payload) =>
    request(`/api/stores/${storeId}`, { method: 'PATCH', body: payload }),
  layout: (storeId) => request(`/api/stores/${storeId}/layout`),
  resetDemo: (storeId) =>
    request(`/api/stores/${storeId}/reset-demo`, {
      method: 'POST',
      body: { confirm: true },
    }),
  createShelf: (storeId, payload) =>
    request(`/api/stores/${storeId}/shelves`, { method: 'POST', body: payload }),
  updateShelf: (shelfId, payload) =>
    request(`/api/shelves/${shelfId}`, { method: 'PATCH', body: payload }),
  deleteShelf: (shelfId) =>
    request(`/api/shelves/${shelfId}`, { method: 'DELETE' }),
  createCategory: (storeId, payload) =>
    request(`/api/stores/${storeId}/categories`, { method: 'POST', body: payload }),
  updateCategory: (categoryId, payload) =>
    request(`/api/categories/${categoryId}`, { method: 'PATCH', body: payload }),
  deleteCategory: (categoryId) =>
    request(`/api/categories/${categoryId}`, { method: 'DELETE' }),
  placeCategory: (categoryId, shelfLevelId, position = null) =>
    request(`/api/categories/${categoryId}/placement`, {
      method: 'PUT',
      body: { shelf_level_id: shelfLevelId, position },
    }),
  query: (text) =>
    request('/api/agent/query', { method: 'POST', body: { text } }),
}

export function mapUrl(storeId, version = '') {
  return `${API_BASE}/api/stores/${storeId}/map.png${version ? `?v=${version}` : ''}`
}
