import { useState } from 'react'

/**
 * Login — email + password form.
 * Calls onLogin(email, password) and shows server errors inline.
 */
export default function Login({ onLogin }) {
  const [email,    setEmail]    = useState('admin@example.com')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onLogin(email.trim().toLowerCase(), password)
    } catch (err) {
      const msg = err?.response?.data?.error || 'Login failed. Check credentials.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h1 style={styles.title}>app_007 Chat</h1>
        <p style={styles.subtitle}>Multi-Tenant Realtime Chat</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoFocus
            style={styles.input}
            placeholder="admin@example.com"
          />

          <label style={styles.label}>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={styles.input}
            placeholder="••••••••"
          />

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

const styles = {
  wrapper: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#0f172a',
  },
  card: {
    background: '#1e293b',
    borderRadius: 12,
    padding: '2.5rem',
    width: '100%',
    maxWidth: 380,
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
  },
  title: {
    margin: 0,
    fontSize: '1.5rem',
    fontWeight: 700,
    color: '#f8fafc',
    letterSpacing: '-0.5px',
  },
  subtitle: {
    margin: '4px 0 2rem',
    fontSize: '0.85rem',
    color: '#64748b',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: 600,
    color: '#94a3b8',
    marginTop: '0.5rem',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  input: {
    padding: '0.65rem 0.85rem',
    borderRadius: 8,
    border: '1px solid #334155',
    background: '#0f172a',
    color: '#f8fafc',
    fontSize: '0.95rem',
    outline: 'none',
  },
  error: {
    margin: '0.5rem 0 0',
    padding: '0.6rem 0.85rem',
    borderRadius: 8,
    background: '#450a0a',
    color: '#fca5a5',
    fontSize: '0.85rem',
  },
  button: {
    marginTop: '1rem',
    padding: '0.75rem',
    borderRadius: 8,
    border: 'none',
    background: '#3b82f6',
    color: '#fff',
    fontWeight: 600,
    fontSize: '0.95rem',
    cursor: 'pointer',
  },
}
