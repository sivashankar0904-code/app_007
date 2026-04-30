/**
 * JWT utilities — all client-side, no library needed.
 * JWTs are base64url-encoded JSON. We decode the payload to read exp/user_id.
 */

/**
 * Decode a JWT without verifying the signature.
 * (Signature verification happens on the server — we just need the payload.)
 */
export function decodeJwt(token) {
  try {
    // JWT = header.payload.signature — we only need the payload (index 1)
    const base64Url = token.split('.')[1]
    const base64    = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}

/** True if the token is expired (or unparseable). */
export function isExpired(token) {
  const payload = decodeJwt(token)
  if (!payload?.exp) return true
  return Date.now() >= payload.exp * 1000
}

/** Milliseconds remaining until the token expires. 0 if already expired. */
export function msUntilExpiry(token) {
  const payload = decodeJwt(token)
  if (!payload?.exp) return 0
  return Math.max(0, payload.exp * 1000 - Date.now())
}

/** Human-readable countdown string, e.g. "4m 32s" */
export function formatTtl(ms) {
  if (ms <= 0) return 'expired'
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}
