import { useState, useEffect, useRef, useCallback } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { msUntilExpiry, formatTtl } from '../utils/jwt'
import { uploadDocument } from '../api'

/**
 * Chat — the main chat room UI.
 *
 * Props:
 *   user        — logged-in user object { username, email, role, org_name }
 *   accessToken — current JWT access token
 *   onLogout    — callback to clear auth state
 *
 * Features:
 *   - Live WebSocket connection with status indicator
 *   - Token TTL countdown — turns red when < 90s
 *   - Document upload via paperclip button (PDF / .txt)
 *   - Upload progress + "AI is processing…" indicator in thread
 *   - Auto-scroll to latest message
 */
export default function Chat({ user, accessToken, onLogout }) {
  const [messages,   setMessages]   = useState([])
  const [input,      setInput]      = useState('')
  const [chatId,     setChatId]     = useState('1')
  const [ttl,        setTtl]        = useState('')
  const [uploading,  setUploading]  = useState(false)
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  const fileRef    = useRef(null)

  // ── Message handler ───────────────────────────────────────────────────────
  const handleMessage = useCallback((data) => {
    if (data.error) {
      setMessages(prev => [...prev, { type: 'error', text: data.error, ts: Date.now() }])
      return
    }

    // User's own question — held private, shown only to them while AI thinks
    if (!data.is_bot && data.is_private) {
      setMessages(prev => [...prev, {
        type:   'question_pending',
        sender: data.sender,
        text:   data.message,
        ts:     Date.now(),
      }])
      return
    }

    // Private bot reply — only the asking user sees this with action buttons
    if (data.is_bot && data.is_private) {
      setMessages(prev => [...prev, {
        type:     'bot_private',
        sender:   data.sender,
        text:     data.message,
        question: data.question ?? '',
        resolved: false,   // true once user picks Keep or Share
        ts:       Date.now(),
      }])
      return
    }

    setMessages(prev => [...prev, {
      type:   data.is_bot ? 'bot' : 'message',
      sender: data.sender,
      text:   data.message,
      mine:   !data.is_bot && data.sender === user.username,
      ts:     Date.now(),
    }])
  }, [user.username])

  const { status, send } = useWebSocket(chatId, accessToken, handleMessage)

  // ── Token TTL countdown ───────────────────────────────────────────────────
  useEffect(() => {
    if (!accessToken) return
    const tick = () => setTtl(formatTtl(msUntilExpiry(accessToken)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [accessToken])

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Send text ─────────────────────────────────────────────────────────────
  const handleSend = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || status !== 'connected') return
    send(text)
    setInput('')
    inputRef.current?.focus()
  }

  // ── Upload file ───────────────────────────────────────────────────────────
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Reset input so same file can be re-selected
    e.target.value = ''

    // Show upload bubble in thread immediately
    const uploadMsgId = Date.now()
    setMessages(prev => [...prev, {
      type:     'upload',
      id:       uploadMsgId,
      fileName: file.name,
      fileSize: formatBytes(file.size),
      state:    'uploading',  // uploading | processing | done | error
      ts:       uploadMsgId,
    }])

    setUploading(true)

    try {
      await uploadDocument(file, chatId)

      // Update bubble: upload done, AI now processing
      setMessages(prev => prev.map(m =>
        m.id === uploadMsgId ? { ...m, state: 'processing' } : m
      ))

      // After a short delay, mark as done
      // In production this would be driven by a WebSocket event from the AI agent
      setTimeout(() => {
        setMessages(prev => prev.map(m =>
          m.id === uploadMsgId ? { ...m, state: 'done' } : m
        ))
      }, 3000)

    } catch (err) {
      const detail = err?.response?.data?.detail
        ?? err?.response?.data?.file?.[0]
        ?? 'Upload failed'

      setMessages(prev => prev.map(m =>
        m.id === uploadMsgId ? { ...m, state: 'error', error: detail } : m
      ))
    } finally {
      setUploading(false)
    }
  }

  // ── Status helpers ────────────────────────────────────────────────────────
  const statusColor = {
    connected:    '#22c55e',
    connecting:   '#f59e0b',
    disconnected: '#ef4444',
    auth_error:   '#ef4444',
  }[status] ?? '#64748b'

  const statusLabel = {
    connected:    'Connected',
    connecting:   'Connecting…',
    disconnected: 'Disconnected',
    auth_error:   'Auth error — token rejected',
  }[status] ?? status

  const ttlMs     = accessToken ? msUntilExpiry(accessToken) : 0
  const ttlDanger = ttlMs > 0 && ttlMs < 90_000

  return (
    <div style={styles.layout}>

      {/* ── Sidebar ── */}
      <aside style={styles.sidebar}>
        <div style={styles.sidebarTop}>
          <h2 style={styles.appName}>app_007</h2>
          <p style={styles.orgName}>{user.org_name ?? 'No org'}</p>
        </div>

        <div style={styles.roomSection}>
          <p style={styles.sectionLabel}>Room</p>
          {['1', '2', '3'].map(id => (
            <button
              key={id}
              onClick={() => { setChatId(id); setMessages([]) }}
              style={{ ...styles.roomBtn, ...(chatId === id ? styles.roomBtnActive : {}) }}
            >
              # chat-{id}
            </button>
          ))}
        </div>

        <div style={styles.sidebarBottom}>
          <div style={styles.userInfo}>
            <span style={styles.avatar}>{user.username[0].toUpperCase()}</span>
            <div>
              <p style={styles.userName}>{user.username}</p>
              <p style={styles.userRole}>{user.role}</p>
            </div>
          </div>
          <button onClick={onLogout} style={styles.logoutBtn}>Sign out</button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={styles.main}>

        {/* Header */}
        <header style={styles.header}>
          <h3 style={styles.roomTitle}># chat-{chatId}</h3>
          <div style={styles.headerRight}>
            <div style={{
              ...styles.ttlBadge,
              background: ttlDanger ? '#450a0a' : '#1e293b',
              color: ttlDanger ? '#fca5a5' : '#94a3b8',
            }}>
              🔑 token: {ttl}
            </div>
            <div style={styles.statusBadge}>
              <span style={{ ...styles.statusDot, background: statusColor }} />
              <span style={{ color: statusColor, fontSize: '0.8rem' }}>{statusLabel}</span>
            </div>
          </div>
        </header>

        {/* Messages */}
        <div style={styles.messages}>
          {messages.length === 0 && (
            <p style={styles.empty}>No messages yet. Say hello 👋</p>
          )}
          {messages.map((msg, i) => {

            if (msg.type === 'error') {
              return <div key={i} style={styles.errorMsg}>⚠ {msg.text}</div>
            }

            if (msg.type === 'upload') {
              return <UploadBubble key={msg.id} msg={msg} />
            }

            // User's own question — visible only to them, dimmed with 🔒
            if (msg.type === 'question_pending') {
              return (
                <div key={msg.ts} style={{ ...styles.msgRow, alignItems: 'flex-end' }}>
                  <div style={styles.questionPendingBubble}>
                    <span style={styles.questionPendingLock}>🔒</span>
                    <span>{msg.text}</span>
                    <span style={styles.questionPendingLabel}>asking AI…</span>
                  </div>
                </div>
              )
            }

            if (msg.type === 'bot_private') {
              return (
                <PrivateBotBubble
                  key={msg.ts}
                  msg={msg}
                  chatId={chatId}
                  accessToken={accessToken}
                  onResolve={(ts, shared) => {
                    if (shared) {
                      // Shared — remove both the pending question bubble and the
                      // private bot bubble (the broadcast will add them back publicly)
                      setMessages(prev =>
                        prev.filter(m =>
                          m.ts !== ts && m.type !== 'question_pending'
                        )
                      )
                    } else {
                      // Kept private — just hide the action buttons
                      setMessages(prev =>
                        prev.map(m => m.ts === ts ? { ...m, resolved: true } : m)
                      )
                    }
                  }}
                />
              )
            }

            if (msg.type === 'bot') {
              return <BotBubble key={i} msg={msg} />
            }

            return (
              <div key={i} style={{ ...styles.msgRow, alignItems: msg.mine ? 'flex-end' : 'flex-start' }}>
                {!msg.mine && <span style={styles.senderLabel}>{msg.sender}</span>}
                <div style={{ ...styles.bubble, ...(msg.mine ? styles.bubbleMine : styles.bubbleOther) }}>
                  {msg.text}
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <form onSubmit={handleSend} style={styles.inputRow}>

          {/* Hidden file input */}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          {/* Paperclip button */}
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading || status !== 'connected'}
            title="Attach a document (PDF or .txt)"
            style={{
              ...styles.attachBtn,
              opacity: (uploading || status !== 'connected') ? 0.4 : 1,
            }}
          >
            📎
          </button>

          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={status === 'connected' ? `Message #chat-${chatId}` : 'Not connected…'}
            disabled={status !== 'connected'}
            style={{ ...styles.textInput, opacity: status !== 'connected' ? 0.5 : 1 }}
          />

          <button
            type="submit"
            disabled={status !== 'connected' || !input.trim()}
            style={styles.sendBtn}
          >
            Send
          </button>
        </form>

      </main>
    </div>
  )
}

// ── Upload bubble component ───────────────────────────────────────────────────

function UploadBubble({ msg }) {
  const stateConfig = {
    uploading:  { icon: '⏫', label: 'Uploading…',        color: '#f59e0b', bg: '#1e293b' },
    processing: { icon: '🤖', label: 'AI is processing…', color: '#818cf8', bg: '#1e1b4b' },
    done:       { icon: '✅', label: 'Ready',              color: '#22c55e', bg: '#1e293b' },
    error:      { icon: '❌', label: 'Failed',             color: '#ef4444', bg: '#450a0a' },
  }
  const cfg = stateConfig[msg.state] ?? stateConfig.uploading

  return (
    <div style={{ ...styles.msgRow, alignItems: 'flex-end' }}>
      <div style={{ ...styles.uploadBubble, background: cfg.bg, borderColor: cfg.color }}>
        <span style={{ fontSize: '1.1rem' }}>{cfg.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={styles.uploadFileName}>{msg.fileName}</p>
          <p style={{ ...styles.uploadMeta, color: cfg.color }}>
            {cfg.label}
            {msg.state === 'done' && <span style={{ color: '#64748b' }}> · {msg.fileSize}</span>}
            {msg.state === 'error' && <span> — {msg.error}</span>}
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Bot bubble component ──────────────────────────────────────────────────────

function BotBubble({ msg }) {
  // Render markdown-style bold (**text**) and bullet points
  const lines = msg.text.split('\n').filter(Boolean)

  return (
    <div style={styles.botWrapper}>
      <div style={styles.botHeader}>
        <span style={styles.botIcon}>🤖</span>
        <span style={styles.botName}>AI Assistant</span>
      </div>
      <div style={styles.botBubble}>
        {lines.map((line, i) => {
          // Bold: **text**
          const formatted = line.replace(/\*\*(.+?)\*\*/g, (_, t) => `<strong>${t}</strong>`)
          return (
            <p
              key={i}
              style={styles.botLine}
              dangerouslySetInnerHTML={{ __html: formatted }}
            />
          )
        })}
      </div>
    </div>
  )
}

// ── Private bot bubble ────────────────────────────────────────────────────────
//
// Shown ONLY to the user who asked the question.
// Two actions:
//   Keep private — removes buttons, message stays visible only to this user
//   Share        — POSTs to /api/chat/share-message/ → broadcasts to whole room

function PrivateBotBubble({ msg, chatId, accessToken, onResolve }) {
  const [sharing, setSharing] = useState(false)
  const [shareErr, setShareErr] = useState('')

  const handleKeep = () => {
    onResolve(msg.ts, false)  // false = not shared, just hide buttons
  }

  const handleShare = async () => {
    setSharing(true)
    setShareErr('')
    try {
      const resp = await fetch('/api/chat/share-message/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // WHY Authorization: share endpoint authenticates via JWT,
          // not the internal key — this is a user action, not a service call
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          chat_id:  parseInt(chatId, 10),
          question: msg.question,
          answer:   msg.text,
        }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.error ?? `HTTP ${resp.status}`)
      }
      onResolve(msg.ts, true)  // true = shared, remove private bubbles entirely
    } catch (e) {
      setShareErr(e.message)
      setSharing(false)
    }
  }

  const lines = msg.text.split('\n').filter(Boolean)

  return (
    <div style={styles.botWrapper}>
      <div style={styles.botHeader}>
        <span style={styles.botIcon}>🤖</span>
        <span style={styles.botName}>AI Assistant</span>
        <span style={styles.privateTag}>🔒 Only you can see this</span>
      </div>

      {/* Question echo */}
      {msg.question && (
        <div style={styles.privateQuestion}>
          <span style={styles.privateQuestionLabel}>Your question: </span>
          {msg.question}
        </div>
      )}

      <div style={{ ...styles.botBubble, ...styles.privateBubble }}>
        {lines.map((line, i) => {
          const formatted = line.replace(/\*\*(.+?)\*\*/g, (_, t) => `<strong>${t}</strong>`)
          return (
            <p
              key={i}
              style={styles.botLine}
              dangerouslySetInnerHTML={{ __html: formatted }}
            />
          )
        })}

        {/* Action buttons — hidden after resolved */}
        {!msg.resolved && (
          <div style={styles.privateActions}>
            <button
              onClick={handleKeep}
              style={styles.keepBtn}
              disabled={sharing}
            >
              🔒 Keep private
            </button>
            <button
              onClick={handleShare}
              style={styles.shareBtn}
              disabled={sharing}
            >
              {sharing ? 'Sharing…' : '💬 Share with team'}
            </button>
            {shareErr && <span style={styles.shareErr}>⚠ {shareErr}</span>}
          </div>
        )}

        {/* After resolved — subtle confirmation */}
        {msg.resolved && (
          <p style={styles.resolvedNote}>✓ Kept private</p>
        )}
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = {
  layout: {
    display: 'flex', height: '100vh',
    background: '#0f172a', color: '#f8fafc',
    fontFamily: 'system-ui, sans-serif',
  },
  // Sidebar
  sidebar: {
    width: 220, minWidth: 220,
    background: '#1e293b', display: 'flex',
    flexDirection: 'column', borderRight: '1px solid #334155',
  },
  sidebarTop:   { padding: '1.25rem 1rem 0.5rem' },
  appName:      { margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' },
  orgName:      { margin: '2px 0 0', fontSize: '0.75rem', color: '#64748b' },
  roomSection:  { padding: '1rem 0.5rem 0.5rem' },
  sectionLabel: {
    margin: '0 0 0.4rem 0.5rem', fontSize: '0.7rem',
    fontWeight: 700, color: '#64748b',
    textTransform: 'uppercase', letterSpacing: '0.08em',
  },
  roomBtn: {
    display: 'block', width: '100%', padding: '0.45rem 0.75rem',
    background: 'none', border: 'none', borderRadius: 6,
    color: '#94a3b8', fontSize: '0.9rem', cursor: 'pointer', textAlign: 'left',
  },
  roomBtnActive:  { background: '#334155', color: '#f8fafc' },
  sidebarBottom:  { marginTop: 'auto', padding: '1rem', borderTop: '1px solid #334155' },
  userInfo:       { display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' },
  avatar: {
    width: 32, height: 32, borderRadius: '50%',
    background: '#3b82f6', display: 'flex',
    alignItems: 'center', justifyContent: 'center',
    fontWeight: 700, fontSize: '0.85rem', color: '#fff', flexShrink: 0,
  },
  userName:  { margin: 0, fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' },
  userRole:  { margin: 0, fontSize: '0.72rem', color: '#64748b', textTransform: 'capitalize' },
  logoutBtn: {
    width: '100%', padding: '0.45rem', borderRadius: 6,
    border: '1px solid #334155', background: 'none',
    color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer',
  },
  // Main
  main:   { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '0.85rem 1.25rem', borderBottom: '1px solid #1e293b',
    background: '#0f172a',
  },
  roomTitle:   { margin: 0, fontSize: '1rem', fontWeight: 600, color: '#f8fafc' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '0.75rem' },
  ttlBadge: {
    padding: '0.3rem 0.65rem', borderRadius: 6,
    fontSize: '0.75rem', fontWeight: 600, fontFamily: 'monospace',
  },
  statusBadge: { display: 'flex', alignItems: 'center', gap: 6 },
  statusDot:   { width: 8, height: 8, borderRadius: '50%' },
  // Messages
  messages: {
    flex: 1, overflowY: 'auto', padding: '1rem 1.25rem',
    display: 'flex', flexDirection: 'column', gap: '0.4rem',
  },
  empty:       { margin: 'auto', color: '#334155', fontSize: '0.9rem' },
  errorMsg:    {
    alignSelf: 'center', padding: '0.4rem 0.85rem', borderRadius: 6,
    background: '#450a0a', color: '#fca5a5', fontSize: '0.8rem',
  },
  msgRow:      { display: 'flex', flexDirection: 'column', gap: 2 },
  senderLabel: { fontSize: '0.72rem', color: '#64748b', marginLeft: 4 },
  // Question pending bubble — user's own question, held private
  questionPendingBubble: {
    display: 'flex', alignItems: 'center', gap: '0.5rem',
    alignSelf: 'flex-end', maxWidth: '65%',
    padding: '0.55rem 0.85rem', borderRadius: 10,
    background: '#1e293b', border: '1px dashed #4b5563',
    color: '#64748b', fontSize: '0.88rem', fontStyle: 'italic',
  },
  questionPendingLock:  { fontSize: '0.8rem', flexShrink: 0 },
  questionPendingLabel: { fontSize: '0.72rem', color: '#4b5563', marginLeft: 4, whiteSpace: 'nowrap' },
  bubble: {
    maxWidth: '65%', padding: '0.55rem 0.85rem', borderRadius: 10,
    fontSize: '0.9rem', lineHeight: 1.45, wordBreak: 'break-word',
  },
  bubbleMine:  { background: '#3b82f6', color: '#fff', alignSelf: 'flex-end', borderBottomRightRadius: 3 },
  bubbleOther: { background: '#1e293b', color: '#e2e8f0', alignSelf: 'flex-start', borderBottomLeftRadius: 3 },
  // Bot bubble
  botWrapper: {
    alignSelf: 'stretch',
    margin: '0.4rem 0',
  },
  botHeader: {
    display: 'flex', alignItems: 'center', gap: '0.4rem',
    marginBottom: '0.35rem',
  },
  botIcon: { fontSize: '1rem' },
  botName: { fontSize: '0.72rem', fontWeight: 700, color: '#818cf8' },
  botBubble: {
    background: '#1e1b4b',
    border: '1px solid #3730a3',
    borderRadius: 10,
    borderTopLeftRadius: 3,
    padding: '0.75rem 1rem',
    maxWidth: '85%',
  },
  botLine: {
    margin: '0.25rem 0',
    fontSize: '0.88rem',
    lineHeight: 1.6,
    color: '#e0e7ff',
  },
  // Private bot bubble
  privateTag: {
    marginLeft: 'auto',
    fontSize: '0.68rem', color: '#a78bfa',
    background: '#2e1065', padding: '2px 7px',
    borderRadius: 4, fontWeight: 600,
  },
  privateQuestion: {
    fontSize: '0.8rem', color: '#94a3b8',
    marginBottom: '0.35rem',
    paddingLeft: 4,
  },
  privateQuestionLabel: {
    fontWeight: 700, color: '#64748b',
  },
  privateBubble: {
    borderColor: '#6d28d9',
    background: '#1a0533',
  },
  privateActions: {
    display: 'flex', alignItems: 'center', gap: '0.5rem',
    marginTop: '0.85rem', flexWrap: 'wrap',
  },
  keepBtn: {
    padding: '0.4rem 0.85rem', borderRadius: 6,
    border: '1px solid #4b5563', background: '#1e293b',
    color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer',
    fontWeight: 600,
  },
  shareBtn: {
    padding: '0.4rem 0.85rem', borderRadius: 6,
    border: 'none', background: '#4f46e5',
    color: '#fff', fontSize: '0.8rem', cursor: 'pointer',
    fontWeight: 600,
  },
  shareErr: {
    fontSize: '0.75rem', color: '#f87171',
  },
  resolvedNote: {
    marginTop: '0.6rem', fontSize: '0.75rem',
    color: '#4b5563', fontStyle: 'italic',
  },
  // Upload bubble
  uploadBubble: {
    display: 'flex', alignItems: 'center', gap: '0.6rem',
    alignSelf: 'flex-end', maxWidth: '65%',
    padding: '0.65rem 0.9rem', borderRadius: 10,
    border: '1px solid', fontSize: '0.85rem',
  },
  uploadFileName: {
    margin: 0, fontWeight: 600, color: '#f8fafc',
    fontSize: '0.85rem', whiteSpace: 'nowrap',
    overflow: 'hidden', textOverflow: 'ellipsis',
  },
  uploadMeta: { margin: '2px 0 0', fontSize: '0.75rem' },
  // Input bar
  inputRow: {
    display: 'flex', gap: '0.5rem',
    padding: '0.85rem 1.25rem',
    borderTop: '1px solid #1e293b', background: '#0f172a',
    alignItems: 'center',
  },
  attachBtn: {
    padding: '0.5rem 0.6rem', borderRadius: 8,
    border: '1px solid #334155', background: 'none',
    cursor: 'pointer', fontSize: '1.1rem', lineHeight: 1,
    flexShrink: 0,
  },
  textInput: {
    flex: 1, padding: '0.65rem 1rem', borderRadius: 8,
    border: '1px solid #334155', background: '#1e293b',
    color: '#f8fafc', fontSize: '0.9rem', outline: 'none',
  },
  sendBtn: {
    padding: '0.65rem 1.25rem', borderRadius: 8, border: 'none',
    background: '#3b82f6', color: '#fff',
    fontWeight: 600, cursor: 'pointer', fontSize: '0.9rem',
  },
}
