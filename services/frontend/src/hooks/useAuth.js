import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api'
import { isExpired, msUntilExpiry } from '../utils/jwt'

/**
 * useAuth — manages login, logout, and automatic token refresh.
 *
 * Token refresh strategy:
 *   - On login:  schedule refresh at (expiry - 60s)
 *   - On mount:  if stored token is valid, resume the schedule; if expired, refresh immediately
 *   - On logout: cancel the timer and clear storage
 *
 * Why 60s before expiry?
 *   Access tokens are short-lived (5 min by default in simplejwt).
 *   Refreshing 60s early ensures we always have a valid token for in-flight WS connections.
 */
export function useAuth() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })
  const [accessToken, setAccessToken] = useState(
    () => localStorage.getItem('access_token')
  )
  const timerRef = useRef(null)

  // ── Core helpers ────────────────────────────────────────────────────────────

  const _persist = (tokens, userData) => {
    localStorage.setItem('access_token',  tokens.access)
    localStorage.setItem('refresh_token', tokens.refresh ?? localStorage.getItem('refresh_token'))
    if (userData) localStorage.setItem('user', JSON.stringify(userData))
  }

  const _scheduleRefresh = useCallback((token, refreshFn) => {
    clearTimeout(timerRef.current)
    // Refresh 60s before expiry, minimum 1s delay
    const delay = Math.max(1000, msUntilExpiry(token) - 60_000)
    timerRef.current = setTimeout(refreshFn, delay)
    console.debug(`[auth] token refresh scheduled in ${Math.round(delay / 1000)}s`)
  }, [])

  // ── Refresh ─────────────────────────────────────────────────────────────────

  const refresh = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) { logout(); return null }

    try {
      const { data } = await api.post('/api/users/token/refresh/', { refresh: refreshToken })
      const newAccess = data.access

      localStorage.setItem('access_token', newAccess)
      setAccessToken(newAccess)
      _scheduleRefresh(newAccess, refresh)

      console.debug('[auth] token refreshed')
      return newAccess
    } catch (err) {
      console.warn('[auth] refresh failed — logging out', err)
      logout()
      return null
    }
  }, [_scheduleRefresh])

  // ── Login ───────────────────────────────────────────────────────────────────

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/api/users/login/', { email, password })
    _persist(data.tokens, data.user)
    setUser(data.user)
    setAccessToken(data.tokens.access)
    _scheduleRefresh(data.tokens.access, refresh)
    return data
  }, [_scheduleRefresh, refresh])

  // ── Logout ──────────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    clearTimeout(timerRef.current)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    setUser(null)
    setAccessToken(null)
  }, [])

  // ── On mount: resume session if token is stored ──────────────────────────────

  useEffect(() => {
    const stored = localStorage.getItem('access_token')
    if (!stored) return

    if (isExpired(stored)) {
      // Try to silently recover using refresh token
      refresh()
    } else {
      _scheduleRefresh(stored, refresh)
    }

    return () => clearTimeout(timerRef.current)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { user, accessToken, login, logout, refresh }
}
