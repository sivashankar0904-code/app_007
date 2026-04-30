import { useAuth } from './hooks/useAuth'
import Login from './components/Login'
import Chat  from './components/Chat'

/**
 * App — top-level routing.
 * No router library needed — we just toggle between Login and Chat
 * based on whether the user is authenticated.
 */
export default function App() {
  const { user, accessToken, login, logout } = useAuth()

  if (!user || !accessToken) {
    return <Login onLogin={login} />
  }

  return (
    <Chat
      user={user}
      accessToken={accessToken}
      onLogout={logout}
    />
  )
}
