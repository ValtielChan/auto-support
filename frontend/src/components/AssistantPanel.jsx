import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const WELCOME =
  "Hi! I'm this mailbox's configuration copilot. Describe your product, ask me to " +
  'write guidelines, change the schedule, manage documents… I apply the changes for you.'

export default function AssistantPanel({ mailboxId, onChanged }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy, open])

  const send = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    try {
      const res = await api.assistantChat(mailboxId, next)
      setMessages([
        ...next,
        { role: 'assistant', content: res.reply, actions: res.actions },
      ])
      if (res.changed) onChanged?.()
    } catch (err) {
      setMessages([
        ...next,
        { role: 'assistant', content: `⚠ ${err.message}`, error: true },
      ])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="assistant-fab" onClick={() => setOpen(true)} title="Open the copilot">
        <i className="fa-solid fa-wand-magic-sparkles" /> Copilot
      </button>
    )
  }

  return (
    <div className="assistant-panel">
      <div className="assistant-head">
        <span>
          <i className="fa-solid fa-wand-magic-sparkles" /> Configuration copilot
        </span>
        <div>
          {messages.length > 0 && (
            <button className="btn btn-small" onClick={() => setMessages([])}>
              Clear
            </button>
          )}
          <button className="btn btn-small" onClick={() => setOpen(false)}>
            ✕
          </button>
        </div>
      </div>
      <div className="assistant-messages">
        <div className="msg msg-assistant">{WELCOME}</div>
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role} ${m.error ? 'msg-error' : ''}`}>
            {m.content}
            {m.actions?.length > 0 && (
              <div className="msg-actions">
                {m.actions.map((a, j) => (
                  <span key={j} className="badge badge-success">✓ {a}</span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg msg-assistant msg-typing">Working…</div>}
        <div ref={bottomRef} />
      </div>
      <form className="assistant-input" onSubmit={send}>
        <textarea
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(e)
            }
          }}
          placeholder="e.g. My product is a todo app for teams — write me a full product context and friendly guidelines"
          disabled={busy}
        />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>
          <i className="fa-solid fa-paper-plane" /> Send
        </button>
      </form>
    </div>
  )
}
