import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * useWebSocket — manages a single WebSocket connection to a chat room.
 *
 * Connection URL: /ws/chat/<chatId>/?token=<accessToken>
 * Vite proxy forwards this to ws://localhost:8000
 *
 * Reconnect strategy:
 *   - Unexpected close (not 1000 / 4001) → retry after 3s
 *   - Close code 4001 = auth failure → do NOT retry (token invalid)
 *   - When accessToken changes (after refresh) → reconnect immediately
 *
 * @param {string|number} chatId     - chat room id
 * @param {string|null}   accessToken - JWT access token; null = don't connect
 * @param {function}      onMessage  - called with parsed JSON for each message
 */
export function useWebSocket(chatId, accessToken, onMessage) {
  const wsRef         = useRef(null)
  const reconnectRef  = useRef(null)
  const onMessageRef  = useRef(onMessage)
  const [status, setStatus] = useState('disconnected') // connected | connecting | disconnected | auth_error

  // Keep onMessage ref fresh so we don't re-create the connect closure on every render
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectRef.current)
    if (wsRef.current) {
      wsRef.current.onclose = null  // prevent reconnect loop on manual close
      wsRef.current.close(1000)
      wsRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!accessToken || !chatId) return
    disconnect()

    setStatus('connecting')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/chat/${chatId}/?token=${accessToken}`
    console.debug('[ws] connecting to', url)

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.debug('[ws] connected')
      setStatus('connected')
      clearTimeout(reconnectRef.current)
    }

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessageRef.current(data)
      } catch {
        console.warn('[ws] non-JSON message received', e.data)
      }
    }

    ws.onclose = (e) => {
      console.debug(`[ws] closed — code ${e.code}`)
      wsRef.current = null

      if (e.code === 4001) {
        // Server rejected our token — stop trying, surface to UI
        setStatus('auth_error')
        return
      }

      setStatus('disconnected')

      if (e.code !== 1000) {
        // Unexpected close — schedule reconnect
        console.debug('[ws] reconnecting in 3s...')
        reconnectRef.current = setTimeout(connect, 3000)
      }
    }

    ws.onerror = (e) => {
      console.warn('[ws] error', e)
      ws.close()
    }
  }, [chatId, accessToken, disconnect])

  // Reconnect whenever accessToken or chatId changes
  useEffect(() => {
    if (accessToken && chatId) {
      connect()
    } else {
      disconnect()
      setStatus('disconnected')
    }
    return disconnect
  }, [chatId, accessToken]) // eslint-disable-line react-hooks/exhaustive-deps

  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message }))
    } else {
      console.warn('[ws] tried to send but socket is not open')
    }
  }, [])

  return { status, send }
}
