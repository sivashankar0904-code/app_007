import axios from 'axios'

/**
 * Axios instance — base URL is '/' so Vite proxy handles routing.
 * The request interceptor injects the Bearer token on every call.
 */
const api = axios.create({ baseURL: '/' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api

/**
 * Upload a document to a chat.
 * Uses multipart/form-data — Django's DocumentUploadView expects this.
 *
 * @param {File}   file   - the file object from the file input
 * @param {string} chatId - which chat this doc belongs to
 * @returns Django document response { id, file, status, uploaded_by, created_at }
 */
export async function uploadDocument(file, chatId) {
  const form = new FormData()
  form.append('file', file)
  form.append('chat', chatId)

  const res = await api.post('/api/documents/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}
