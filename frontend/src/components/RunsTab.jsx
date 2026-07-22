import { useEffect, useState } from 'react'
import { api, fmtDate } from '../api.js'
import { Alert, Badge, Spinner } from './ui.jsx'

export default function RunsTab({ mailboxId }) {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState(null)

  const load = () =>
    api.listRuns({ mailbox_id: mailboxId }).then(setRuns).catch((e) => setError(e.message))

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [mailboxId])

  if (error) return <Alert>{error}</Alert>
  if (!runs) return <Spinner />

  return (
    <div className="card">
      <h2>Run history</h2>
      {runs.length === 0 ? (
        <p className="muted">No runs yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Finished</th>
              <th>Trigger</th>
              <th>Status</th>
              <th>Fetched</th>
              <th>Processed</th>
              <th>Sent</th>
              <th>Drafts</th>
              <th>Escalated</th>
              <th>Report</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <RunRow
                key={r.id}
                run={r}
                open={openId === r.id}
                onToggle={() => setOpenId(openId === r.id ? null : r.id)}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function RunRow({ run, open, onToggle }) {
  const report = run.report || []
  return (
    <>
      <tr>
        <td>{fmtDate(run.started_at)}</td>
        <td>{fmtDate(run.finished_at)}</td>
        <td>{run.trigger}</td>
        <td>
          <Badge value={run.status} />
          {run.error && <div className="error-inline">{run.error}</div>}
        </td>
        <td>{run.emails_fetched}</td>
        <td>{run.emails_processed}</td>
        <td>{run.replies_sent}</td>
        <td>{run.drafts_created}</td>
        <td>{run.escalated}</td>
        <td>
          {report.length === 0 ? (
            <span className="muted">—</span>
          ) : (
            <button className="btn btn-ghost" onClick={onToggle}>
              {open ? 'Hide' : `View (${report.length})`}
            </button>
          )}
        </td>
      </tr>
      {open && report.length > 0 && (
        <tr>
          <td colSpan={10}>
            <table>
              <thead>
                <tr>
                  <th>From</th>
                  <th>Subject</th>
                  <th>Category</th>
                  <th>Outcome</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {report.map((e) => (
                  <tr key={e.email_id}>
                    <td>{e.from_address}</td>
                    <td>{e.subject || <span className="muted">(no subject)</span>}</td>
                    <td>{e.category ? <Badge value={e.category} /> : <span className="muted">—</span>}</td>
                    <td><Badge value={e.status} /></td>
                    <td>{e.reason || <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  )
}
