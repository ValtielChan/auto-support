import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alert, Field, Spinner } from './ui.jsx'

const LABELS = {
  playbook: {
    heading: 'Response playbooks',
    intro:
      'Tell the agent how to handle each type of email it receives. One playbook per situation - the agent follows the one that matches an incoming email.',
    titleLabel: 'Situation / email type',
    titleHint: 'e.g. "Support request from a user", "SEO cold outreach", "Marketplace partner"',
    titlePlaceholder: 'When the agent receives…',
    bodyLabel: 'What the agent should do',
    bodyPlaceholder: 'Describe the desired handling: reply, escalate, ignore, ask for details…',
    addLabel: 'Add playbook',
    empty: 'No playbooks yet - add one per type of email you want handled a certain way.',
  },
  fact: {
    heading: 'Product facts',
    intro:
      'Concrete, authoritative specifics about your product the agent can rely on to resolve requests: technical details, limits, pricing, usage conditions… Keep each fact short and factual.',
    titleLabel: 'Topic',
    titleHint: 'e.g. "Free plan limits", "Supported export formats", "Refund policy"',
    titlePlaceholder: 'Short topic…',
    bodyLabel: 'Detail',
    bodyPlaceholder: 'The precise fact the agent may use…',
    addLabel: 'Add fact',
    empty: 'No product facts yet - add the specifics the agent can use to unblock requests.',
  },
}

export default function KnowledgeTab({ mailboxId }) {
  return (
    <div className="stack">
      <KnowledgeSection mailboxId={mailboxId} kind="playbook" />
      <KnowledgeSection mailboxId={mailboxId} kind="fact" />
    </div>
  )
}

function KnowledgeSection({ mailboxId, kind }) {
  const t = LABELS[kind]
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () =>
    api.listKnowledge(mailboxId, kind).then(setItems).catch((e) => setError(e.message))
  useEffect(() => {
    load()
  }, [mailboxId, kind])

  const add = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.addKnowledge(mailboxId, { kind, title, body })
      setTitle('')
      setBody('')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!items) return error ? <Alert>{error}</Alert> : <Spinner />

  return (
    <div className="card">
      <h2>{t.heading}</h2>
      <p className="muted">{t.intro}</p>
      <Alert>{error}</Alert>

      {items.length === 0 ? (
        <p className="muted">{t.empty}</p>
      ) : (
        <div className="stack">
          {items.map((item) => (
            <ItemEditor key={item.id} item={item} labels={t} onChanged={load} onError={setError} />
          ))}
        </div>
      )}

      <form onSubmit={add} className="knowledge-add">
        <Field label={t.titleLabel} hint={t.titleHint}>
          <input
            required
            value={title}
            placeholder={t.titlePlaceholder}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label={t.bodyLabel}>
          <textarea
            required
            rows={3}
            value={body}
            placeholder={t.bodyPlaceholder}
            onChange={(e) => setBody(e.target.value)}
          />
        </Field>
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Adding…' : t.addLabel}
          </button>
        </div>
      </form>
    </div>
  )
}

function ItemEditor({ item, labels, onChanged, onError }) {
  const [title, setTitle] = useState(item.title)
  const [body, setBody] = useState(item.body)
  const [busy, setBusy] = useState(false)
  const dirty = title !== item.title || body !== item.body

  const save = async () => {
    setBusy(true)
    onError('')
    try {
      await api.updateKnowledge(item.id, { title, body })
      onChanged()
    } catch (e) {
      onError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!window.confirm(`Delete "${item.title}"?`)) return
    onError('')
    try {
      await api.deleteKnowledge(item.id)
      onChanged()
    } catch (e) {
      onError(e.message)
    }
  }

  return (
    <div className="knowledge-item">
      <Field label={labels.titleLabel}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field label={labels.bodyLabel}>
        <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
      </Field>
      <div className="row-actions">
        <button className="btn btn-small" disabled={!dirty || busy} onClick={save}>
          {busy ? 'Saving…' : dirty ? 'Save' : 'Saved'}
        </button>
        <button className="btn btn-small btn-danger" onClick={remove}>
          Delete
        </button>
      </div>
    </div>
  )
}
