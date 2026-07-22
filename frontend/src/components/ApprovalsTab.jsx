import { useEffect, useState } from 'react'
import { api, fmtDate } from '../api.js'
import { Alert, Spinner } from './ui.jsx'

function DraftCard({ draft, onDone, onError }) {
  const [body, setBody] = useState(draft.body)
  const [busy, setBusy] = useState('')
  const [showOriginal, setShowOriginal] = useState(false)
  const dirty = body !== draft.body

  const act = async (action) => {
    setBusy(action)
    try {
      if (dirty) await api.updateReply(draft.id, body)
      if (action === 'approve') await api.approveReply(draft.id)
      if (action === 'reject') await api.rejectReply(draft.id)
      if (action === 'save') onError('')
      onDone(action)
    } catch (e) {
      onError(e.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="card draft-card">
      <div className="draft-head">
        <div>
          <strong>{draft.email.subject || '(no subject)'}</strong>
          <div className="muted">
            From {draft.email.from_address} · {fmtDate(draft.email.received_at)}
          </div>
        </div>
        <button className="btn btn-small" onClick={() => setShowOriginal((v) => !v)}>
          {showOriginal ? 'Hide original' : 'Show original'}
        </button>
      </div>
      {showOriginal && <pre className="email-body">{draft.email.body_text}</pre>}
      <textarea rows={10} value={body} onChange={(e) => setBody(e.target.value)} />
      <div className="actions">
        {dirty && (
          <button className="btn" onClick={() => act('save')} disabled={busy !== ''}>
            {busy === 'save' ? 'Saving…' : 'Save edit'}
          </button>
        )}
        <button className="btn btn-danger" onClick={() => act('reject')} disabled={busy !== ''}>
          <i className="fa-solid fa-xmark" /> {busy === 'reject' ? 'Rejecting…' : 'Reject'}
        </button>
        <button className="btn btn-primary" onClick={() => act('approve')} disabled={busy !== ''}>
          <i className="fa-solid fa-paper-plane" />{' '}
          {busy === 'approve' ? 'Sending…' : 'Approve & send'}
        </button>
      </div>
    </div>
  )
}

export default function ApprovalsTab({ mailboxId }) {
  const [drafts, setDrafts] = useState(null)
  const [error, setError] = useState('')

  const load = () =>
    api.listReplies('draft', mailboxId).then(setDrafts).catch((e) => setError(e.message))
  useEffect(() => {
    setDrafts(null)
    load()
  }, [mailboxId])

  if (!drafts) return error ? <Alert>{error}</Alert> : <Spinner />

  return (
    <div className="stack">
      <div className="section-head">
        <h2>Approval queue</h2>
        <span className="muted">{drafts.length} draft(s) waiting</span>
      </div>
      <Alert>{error}</Alert>
      {drafts.length === 0 ? (
        <div className="card empty">
          <p>Nothing to approve. 🎉</p>
          <p className="muted">Drafts appear here when the agent runs with auto-send disabled.</p>
        </div>
      ) : (
        drafts.map((d) => <DraftCard key={d.id} draft={d} onError={setError} onDone={() => load()} />)
      )}
    </div>
  )
}
