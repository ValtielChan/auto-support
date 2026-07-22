import { useEffect, useRef, useState } from 'react'
import { api, fmtDate } from '../api.js'
import { Alert, Badge, Modal, Spinner } from './ui.jsx'

export default function InboxTab({ mailboxId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(() => new Set())
  const [openUid, setOpenUid] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    setError('')
    return api
      .listInbox(mailboxId)
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    setItems(null)
    setOpenUid(null)
    load()
  }, [mailboxId])

  if (error && !items) return <Alert>{error}</Alert>
  if (!items) return <Spinner />

  const unreadCount = items.filter((m) => !m.seen).length
  const toggle = (uid) =>
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(uid) ? next.delete(uid) : next.add(uid)
      return next
    })
  const allSelected = items.length > 0 && selected.size === items.length
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(items.map((m) => m.uid)))

  const runBulk = async (fn) => {
    setBusy(true)
    setError('')
    try {
      await fn([...selected])
      setSelected(new Set())
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  const markSeen = (seen) => runBulk((uids) => api.setInboxFlags(mailboxId, uids, seen))
  const bulkDelete = () => {
    if (!window.confirm(`Permanently delete ${selected.size} message(s) from the mailbox?`)) return
    runBulk((uids) => api.deleteInboxMessages(mailboxId, uids))
  }

  return (
    <div className="inbox-split">
      <div className="inbox-list-pane">
        <div className="inbox-list-head">
          <h2>Inbox</h2>
          <span className="muted">
            {items.length} · {unreadCount} unread
          </span>
          <button className="btn btn-small" onClick={load} disabled={busy}>
            <i className="fa-solid fa-rotate" /> Refresh
          </button>
        </div>

        {selected.size > 0 && (
          <div className="inbox-bulk">
            <strong>{selected.size} selected</strong>
            <button className="btn btn-small" onClick={() => markSeen(true)} disabled={busy}>
              Mark read
            </button>
            <button className="btn btn-small" onClick={() => markSeen(false)} disabled={busy}>
              Mark unread
            </button>
            <button className="btn btn-small btn-danger" onClick={bulkDelete} disabled={busy}>
              Delete
            </button>
          </div>
        )}

        <div className="inbox-list-scroll">
          {items.length === 0 ? (
            <p className="muted inbox-empty">The mailbox is empty.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th className="inbox-check">
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                  </th>
                  <th />
                  <th>From</th>
                  <th>Subject</th>
                  <th>Agent</th>
                </tr>
              </thead>
              <tbody>
                {items.map((m) => (
                  <tr
                    key={m.uid}
                    className={`${m.seen ? '' : 'inbox-row-unread'} ${openUid === m.uid ? 'inbox-row-open' : ''}`}
                  >
                    <td className="inbox-check">
                      <input
                        type="checkbox"
                        checked={selected.has(m.uid)}
                        onChange={() => toggle(m.uid)}
                      />
                    </td>
                    <td>
                      <span className={`inbox-dot ${m.seen ? 'read' : ''}`} title={m.seen ? 'Read' : 'Unread'} />
                    </td>
                    <td className="inbox-clickable" onClick={() => setOpenUid(m.uid)}>
                      <div className="inbox-from">{m.from_address || '-'}</div>
                      <div className="muted inbox-date">{fmtDate(m.received_at)}</div>
                    </td>
                    <td className="inbox-clickable" onClick={() => setOpenUid(m.uid)}>
                      {m.subject || <span className="muted">(no subject)</span>}
                    </td>
                    <td className="inbox-clickable" onClick={() => setOpenUid(m.uid)}>
                      <AgentCell m={m} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="inbox-reader-pane">
        {openUid !== null ? (
          <MessageReader
            key={openUid}
            mailboxId={mailboxId}
            uid={openUid}
            onClose={() => setOpenUid(null)}
            onChanged={load}
          />
        ) : (
          <div className="inbox-empty">
            <i className="fa-solid fa-envelope-open fa-2x" />
            <p className="muted">Select a message to read and reply.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function AgentCell({ m }) {
  if (!m.agent_status) return <span className="badge badge-muted">Not processed</span>
  if (m.agent_status === 'new') return <span className="badge badge-new">Pending</span>
  return (
    <div className="badge-row">
      <Badge value={m.agent_status} />
      {m.agent_category && <Badge value={m.agent_category} />}
    </div>
  )
}

function AgentActivity({ agent }) {
  if (!agent) return <p className="muted">The agent has not processed this message yet.</p>
  const replyLabel = (s) =>
    ({ sent: 'Reply sent', draft: 'Draft reply (awaiting approval)', rejected: 'Reply rejected' }[s] ||
      `Reply (${s})`)
  return (
    <div className="inbox-agent">
      <h3>Agent activity</h3>
      <div className="badge-row">
        <Badge value={agent.status} />
        {agent.category && <Badge value={agent.category} />}
        {agent.processed_at && <span className="muted">· processed {fmtDate(agent.processed_at)}</span>}
      </div>
      {agent.category_reason && (
        <p>
          <strong>Classification:</strong> {agent.category_reason}
        </p>
      )}
      {agent.action_reason && (
        <p>
          <strong>Decision:</strong> {agent.action_reason}
        </p>
      )}
      {agent.error && <p className="error-inline">Error: {agent.error}</p>}
      <p className="muted">
        Ingested {fmtDate(agent.fetched_at)} · email #{agent.email_id}
      </p>
      {agent.replies.map((r, i) => (
        <div key={i} className="inbox-reply-log">
          <p>
            <strong>{replyLabel(r.status)}</strong>{' '}
            <span className="muted">
              · {fmtDate(r.created_at)}
              {r.sent_at ? ` · sent ${fmtDate(r.sent_at)}` : ''}
              {r.model_used ? ` · ${r.model_used}` : ''}
            </span>
          </p>
          <pre className="inbox-body">{r.body}</pre>
        </div>
      ))}
    </div>
  )
}

// Renders untrusted email HTML inside a locked-down iframe (no allow-scripts, so
// nothing in the email can run JS), auto-sized to its content. allow-same-origin
// lets us read the doc height; allow-popups lets links open in a new tab.
function HtmlEmail({ html }) {
  const ref = useRef(null)
  const srcDoc =
    '<!doctype html><html><head><meta charset="utf-8"><base target="_blank">' +
    '<style>html{overflow-x:auto}body{margin:10px;font-family:Arial,Helvetica,sans-serif;' +
    'color:#111;word-break:break-word}img{max-width:100%;height:auto}</style></head><body>' +
    html +
    '</body></html>'

  const resize = () => {
    const f = ref.current
    try {
      const doc = f?.contentDocument
      if (doc) f.style.height = Math.min(doc.body.scrollHeight + 24, 4000) + 'px'
    } catch {
      /* cross-origin: leave default height */
    }
  }

  return (
    <iframe
      ref={ref}
      title="Email"
      className="email-frame"
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      srcDoc={srcDoc}
      onLoad={() => {
        resize()
        setTimeout(resize, 400)
        setTimeout(resize, 1200)
      }}
    />
  )
}

function MessageReader({ mailboxId, uid, onClose, onChanged }) {
  const [msg, setMsg] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [view, setView] = useState('html')

  useEffect(() => {
    setMsg(null)
    api.getInboxMessage(mailboxId, uid).then(setMsg).catch((e) => setError(e.message))
  }, [mailboxId, uid])

  const act = async (key, fn) => {
    setBusy(key)
    setError('')
    try {
      await fn()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }
  const markSeen = (seen) =>
    act(seen ? 'read' : 'unread', async () => {
      await api.setInboxFlags(mailboxId, [uid], seen)
      setMsg((m) => ({ ...m, seen }))
      onChanged()
    })
  const del = () =>
    act('delete', async () => {
      if (!window.confirm('Permanently delete this message from the mailbox?')) return
      await api.deleteInboxMessages(mailboxId, [uid])
      onChanged()
      onClose()
    })

  return (
    <div className="reader">
      <div className="reader-head">
        <div className="inbox-head">
          <h2>{msg ? msg.subject || '(no subject)' : 'Loading…'}</h2>
          <button className="btn btn-small" onClick={onClose}>
            Close
          </button>
        </div>
        {msg && (
          <>
            <p className="muted reader-from">
              From <strong>{msg.from_address}</strong> · {fmtDate(msg.received_at)} ·{' '}
              {msg.seen ? 'Read' : 'Unread'}
            </p>
            <div className="row-actions inbox-msg-actions">
              <button className="btn btn-small" onClick={() => markSeen(!msg.seen)} disabled={!!busy}>
                {busy === 'read' || busy === 'unread' ? '…' : msg.seen ? 'Mark unread' : 'Mark read'}
              </button>
              <button className="btn btn-small btn-danger" onClick={del} disabled={!!busy}>
                {busy === 'delete' ? '…' : 'Delete'}
              </button>
            </div>
          </>
        )}
      </div>

      <Alert>{error}</Alert>

      {!msg ? (
        <Spinner />
      ) : (
        <>
          <div className="reader-scroll">
            <AgentActivity agent={msg.agent} />
            <div className="reader-msg-head">
              <h3>Message</h3>
              {msg.body_html && (
                <div className="viewtoggle">
                  <button
                    className={`btn btn-small ${view === 'html' ? 'btn-active' : ''}`}
                    onClick={() => setView('html')}
                  >
                    Rich
                  </button>
                  <button
                    className={`btn btn-small ${view === 'text' ? 'btn-active' : ''}`}
                    onClick={() => setView('text')}
                  >
                    Text
                  </button>
                </div>
              )}
            </div>
            {view === 'html' && msg.body_html ? (
              <HtmlEmail html={msg.body_html} />
            ) : (
              <div className="reader-body">{msg.body_text || '(empty body)'}</div>
            )}
          </div>
          <Composer mailboxId={mailboxId} uid={uid} to={msg.from_address} />
        </>
      )}
    </div>
  )
}

// --- BBCode composer with a live preview and AI drafting -------------------

const AI_CHIPS = [
  ['Answer the request', 'Answer the request helpfully and completely.'],
  ['Politely decline', 'Politely decline this request.'],
  ['Ask for details', 'Ask for the specific information needed to help.'],
  ['Thank them', 'Thank the sender warmly and briefly.'],
]

function bbToHtml(t) {
  let s = (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const safe = (u) => (/^(https?:|mailto:)/i.test(u) ? u : '#')
  s = s.replace(/\[url=([^\]\s]+)\]([\s\S]+?)\[\/url\]/gi, (m, u, l) => `<a href="${safe(u)}">${l}</a>`)
  s = s.replace(/\[url\]([^\[]+?)\[\/url\]/gi, (m, u) => `<a href="${safe(u)}">${u}</a>`)
  s = s.replace(/\[b\]([\s\S]+?)\[\/b\]/gi, '<strong>$1</strong>')
  s = s.replace(/\[i\]([\s\S]+?)\[\/i\]/gi, '<em>$1</em>')
  s = s.replace(/\[u\]([\s\S]+?)\[\/u\]/gi, '<u>$1</u>')
  s = s.replace(/\[list\]([\s\S]+?)\[\/list\]/gi, (m, inner) =>
    '<ul>' +
    inner
      .split(/\[\*\]/)
      .map((x) => x.trim())
      .filter(Boolean)
      .map((x) => `<li>${x}</li>`)
      .join('') +
    '</ul>'
  )
  return s.replace(/\n/g, '<br>')
}

function Composer({ mailboxId, uid, to }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [customOpen, setCustomOpen] = useState(false)
  const [customText, setCustomText] = useState('')
  const ref = useRef(null)

  const run = async (key, fn) => {
    setBusy(key)
    setError('')
    try {
      await fn()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }
  const surround = (o, c) => {
    const ta = ref.current
    if (!ta) return
    const { selectionStart: a, selectionEnd: b, value } = ta
    setText(value.slice(0, a) + o + value.slice(a, b) + c + value.slice(b))
    setSent(false)
    requestAnimationFrame(() => {
      ta.focus()
      ta.selectionStart = a + o.length
      ta.selectionEnd = b + o.length
    })
  }
  const ai = (key, instruction) =>
    run(key, async () => {
      const r = await api.suggestReply(mailboxId, uid, instruction)
      setText(r.body || '')
      setPreview(false)
    })
  const submitCustom = () => {
    const instruction = customText.trim()
    if (!instruction) return
    setCustomOpen(false)
    setCustomText('')
    ai('ai-custom', instruction)
  }
  const send = () =>
    run('send', async () => {
      await api.replyInboxMessage(mailboxId, uid, text)
      setText('')
      setPreview(false)
      setOpen(false)
      setSent(true)
    })
  const cancel = () => {
    if (text.trim() && !window.confirm('Discard this reply?')) return
    setText('')
    setPreview(false)
    setError('')
    setOpen(false)
  }
  const startAi = (key, instruction) => {
    setSent(false)
    setOpen(true)
    ai(key, instruction)
  }

  const aiBusy = busy.startsWith('ai')

  // Collapsed: no composer chrome - just entry points, so the message has room.
  if (!open) {
    return (
      <div className="reader-compose reader-compose-bar">
        {sent && <Alert kind="success">Reply sent.</Alert>}
        <button className="btn btn-primary" onClick={() => { setSent(false); setOpen(true) }}>
          <i className="fa-solid fa-reply" /> Reply
        </button>
        <span className="muted composer-hint">or draft with AI:</span>
        <button className="chip" disabled={aiBusy} onClick={() => startAi('ai-Answer the request', AI_CHIPS[0][1])}>
          {aiBusy ? '…' : 'Answer'}
        </button>
        <button className="chip" disabled={aiBusy} onClick={() => startAi('ai-Politely decline', AI_CHIPS[1][1])}>
          {aiBusy ? '…' : 'Decline'}
        </button>
      </div>
    )
  }

  return (
    <div className="reader-compose">
      <div className="composer-toolbar">
        <button type="button" className="btn btn-small" title="Bold" onClick={() => surround('[b]', '[/b]')}>
          <i className="fa-solid fa-bold" />
        </button>
        <button type="button" className="btn btn-small" title="Italic" onClick={() => surround('[i]', '[/i]')}>
          <i className="fa-solid fa-italic" />
        </button>
        <button type="button" className="btn btn-small" title="Underline" onClick={() => surround('[u]', '[/u]')}>
          <i className="fa-solid fa-underline" />
        </button>
        <button type="button" className="btn btn-small" title="Link" onClick={() => surround('[url=https://]', '[/url]')}>
          <i className="fa-solid fa-link" />
        </button>
        <button type="button" className="btn btn-small" title="List item" onClick={() => surround('[list]\n[*]', '\n[/list]')}>
          <i className="fa-solid fa-list-ul" />
        </button>
        <span className="composer-spacer" />
        <button type="button" className={`btn btn-small ${preview ? 'btn-active' : ''}`} onClick={() => setPreview((p) => !p)}>
          {preview ? 'Edit' : 'Preview'}
        </button>
      </div>

      <div className="composer-ai">
        <span className="composer-ai-label">
          <i className="fa-solid fa-wand-magic-sparkles" /> AI
        </span>
        {AI_CHIPS.map(([label, instr]) => (
          <button
            key={label}
            type="button"
            className="chip"
            disabled={aiBusy}
            onClick={() => ai(`ai-${label}`, instr)}
          >
            {busy === `ai-${label}` ? '…' : label}
          </button>
        ))}
        <button type="button" className="chip" disabled={aiBusy} onClick={() => setCustomOpen(true)}>
          {busy === 'ai-custom' ? '…' : 'Custom…'}
        </button>
      </div>

      {customOpen && (
        <Modal title="Draft with AI" onClose={() => setCustomOpen(false)}>
          <p className="muted">Tell the AI how to write this reply - it uses the mailbox's product context, playbooks and guidelines.</p>
          <textarea
            rows={4}
            autoFocus
            className="composer-text"
            value={customText}
            placeholder="e.g. Offer a 20% discount and apologise for the delay"
            onChange={(e) => setCustomText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submitCustom()
            }}
          />
          <div className="actions composer-actions">
            <button className="btn" onClick={() => setCustomOpen(false)}>
              Cancel
            </button>
            <button className="btn btn-primary" disabled={!customText.trim() || aiBusy} onClick={submitCustom}>
              {aiBusy ? 'Writing…' : 'Write reply'}
            </button>
          </div>
        </Modal>
      )}

      <Alert>{error}</Alert>

      {preview ? (
        <div
          className="composer-preview"
          dangerouslySetInnerHTML={{ __html: bbToHtml(text) || '<span class="muted">Nothing to preview</span>' }}
        />
      ) : (
        <textarea
          ref={ref}
          className="composer-text"
          rows={5}
          value={text}
          placeholder={`Reply to ${to}…  (BBCode: [b] [i] [u] [url] [list][*])`}
          onChange={(e) => {
            setText(e.target.value)
            setSent(false)
          }}
        />
      )}

      <div className="actions composer-actions">
        <button className="btn" onClick={cancel} disabled={busy === 'send'}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={send} disabled={!!busy || !text.trim()}>
          {busy === 'send' ? 'Sending…' : 'Send reply'}
        </button>
      </div>
    </div>
  )
}
