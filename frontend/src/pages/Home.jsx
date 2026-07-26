import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import TopBar from '../components/TopBar.jsx'
import { Alert, Badge, Spinner } from '../components/ui.jsx'

export default function Home() {
  const [mailboxes, setMailboxes] = useState(null)
  const [error, setError] = useState('')
  const [importing, setImporting] = useState(false)
  const fileRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.listMailboxes().then(setMailboxes).catch((e) => setError(e.message))
  }, [])

  const onImportFile = async (e) => {
    const file = e.target.files && e.target.files[0]
    e.target.value = ''
    if (!file) return
    setImporting(true)
    setError('')
    try {
      const data = JSON.parse(await file.text())
      const mb = await api.importMailbox(data)
      // Land on the edit screen: the user reviews the connection and re-enters
      // passwords when the export was made without secrets.
      navigate(`/m/${mb.id}/edit`)
    } catch (err) {
      setError(err instanceof SyntaxError ? 'Not a valid export file (invalid JSON)' : err.message)
      setImporting(false)
    }
  }

  return (
    <div className="simple-shell">
      <TopBar />
      <div className="simple-main">
        <div className="page-narrow">
          <div className="page-head">
            <h1>Your mailboxes</h1>
            <div className="actions">
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                hidden
                onChange={onImportFile}
              />
              <button
                className="btn"
                onClick={() => fileRef.current.click()}
                disabled={importing}
              >
                <i className="fa-solid fa-file-import" /> {importing ? 'Importing…' : 'Import'}
              </button>
              <Link to="/mailboxes/new" className="btn btn-primary">
                <i className="fa-solid fa-plus" /> Add mailbox
              </Link>
            </div>
          </div>
          <Alert>{error}</Alert>
          {!mailboxes ? (
            <Spinner />
          ) : mailboxes.length === 0 ? (
            <div className="card empty">
              <p>No mailbox yet.</p>
              <p className="muted">Add an existing IMAP/SMTP mailbox, then configure its support agent.</p>
            </div>
          ) : (
            <div className="brand-grid">
              {mailboxes.map((m) => (
                <Link key={m.id} to={`/m/${m.id}`} className="brand-card">
                  <div className="brand-card-name">{m.name}</div>
                  <div className="muted brand-card-addr">{m.email_address}</div>
                  <div className="brand-card-foot">
                    <Badge value={m.active ? 'success' : 'ignored'} />
                    <span className="brand-card-enter">
                      Open <i className="fa-solid fa-arrow-right" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
