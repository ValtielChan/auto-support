import { useEffect, useState } from 'react'
import { api, fmtDate } from '../api.js'
import ModelSelect from './ModelSelect.jsx'
import { Alert, Field, Spinner } from './ui.jsx'

const INTERVALS = [
  [15, 'Every 15 minutes'],
  [30, 'Every 30 minutes'],
  [60, 'Every hour'],
  [180, 'Every 3 hours'],
  [720, 'Every 12 hours'],
  [1440, 'Every 24 hours'],
  [2880, 'Every 48 hours'],
]

export default function AgentTab({ mailboxId }) {
  const [agent, setAgent] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.getAgent(mailboxId).then(setAgent).catch((e) => setError(e.message))
  }, [mailboxId])

  if (!agent) return error ? <Alert>{error}</Alert> : <Spinner />

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setAgent((a) => ({ ...a, [key]: value }))
    setSaved(false)
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setAgent(await api.saveAgent(mailboxId, agent))
      setSaved(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <Alert>{error}</Alert>
      {saved && <Alert kind="success">Agent configuration saved.</Alert>}

      <div className="card">
        <h2>Schedule & behavior</h2>
        <label className="checkbox">
          <input type="checkbox" checked={agent.enabled} onChange={set('enabled')} />{' '}
          <strong>Agent enabled</strong> - reads and processes new emails automatically
        </label>
        <div className="grid-3">
          <Field label="Check interval">
            <select
              value={agent.interval_minutes}
              onChange={(e) =>
                setAgent((a) => ({ ...a, interval_minutes: Number(e.target.value) }))
              }
            >
              {INTERVALS.map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
              {!INTERVALS.some(([v]) => v === agent.interval_minutes) && (
                <option value={agent.interval_minutes}>
                  Every {agent.interval_minutes} minutes
                </option>
              )}
            </select>
          </Field>
          <Field label="Model" hint="The list follows the provider configured in Settings">
            <ModelSelect
              value={agent.model || ''}
              onChange={(m) => {
                setAgent((a) => ({ ...a, model: m || null }))
                setSaved(false)
              }}
              defaultLabel="Platform default"
            />
          </Field>
          <Field label="Reply language" hint="Blank = same language as the customer">
            <input value={agent.language || ''} onChange={set('language')} placeholder="e.g. French" />
          </Field>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={agent.auto_send} onChange={set('auto_send')} />{' '}
          <strong>Auto-send replies</strong> - if unchecked, replies wait in the approval queue
        </label>
        <p className="muted">Last run: {fmtDate(agent.last_run_at)}</p>
      </div>

      <div className="card">
        <h2>Product context</h2>
        <p className="muted">
          A general overview of what this mailbox supports: the product/service and what it does.
          Put per-situation rules and concrete product specifics in the <strong>Knowledge</strong>{' '}
          tab (playbooks &amp; facts), and long-form material in the <strong>Documents</strong> tab.
        </p>
        <textarea rows={8} value={agent.product_context} onChange={set('product_context')} />
      </div>

      <div className="card">
        <h2>Writing style &amp; tone</h2>
        <p className="muted">
          Only <em>how</em> the agent writes: voice, tone, formatting, phrasings to use or avoid.
          What to <em>do</em> for each type of email belongs in the Knowledge tab's playbooks.
        </p>
        <textarea rows={6} value={agent.guidelines} onChange={set('guidelines')} />
        <Field label="Signature" hint="Appended to every reply exactly as written">
          <textarea rows={3} value={agent.signature} onChange={set('signature')} />
        </Field>
      </div>

      <div className="card">
        <h2>Escalation to a human</h2>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={agent.escalation_enabled}
            onChange={set('escalation_enabled')}
          />{' '}
          Allow the agent to escalate emails it cannot resolve
        </label>
        {agent.escalation_enabled && (
          <>
            <div className="grid-2">
              <Field label="Escalation email" hint="Where escalated emails are forwarded (e.g. your technical team)">
                <input
                  required
                  type="email"
                  value={agent.escalation_email || ''}
                  onChange={set('escalation_email')}
                />
              </Field>
            </div>
            <Field label="Escalation criteria" hint="Optional: specific situations that must always be escalated">
              <textarea
                rows={4}
                value={agent.escalation_criteria}
                onChange={set('escalation_criteria')}
              />
            </Field>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={agent.notify_customer_on_escalation}
                onChange={set('notify_customer_on_escalation')}
              />{' '}
              Tell the customer their request was forwarded to the team
            </label>
          </>
        )}
      </div>

      <div className="actions">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save agent'}
        </button>
      </div>
    </form>
  )
}
