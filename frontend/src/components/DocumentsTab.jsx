import { useEffect, useRef, useState } from 'react'
import { api, fmtDate } from '../api.js'
import { Alert, Field, Spinner } from './ui.jsx'

export default function DocumentsTab({ mailboxId }) {
  const [docs, setDocs] = useState(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)

  const load = () => api.listDocuments(mailboxId).then(setDocs).catch((e) => setError(e.message))
  useEffect(() => {
    load()
  }, [mailboxId])

  if (!docs) return error ? <Alert>{error}</Alert> : <Spinner />

  const importFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setContent(String(reader.result))
      if (!title) setTitle(file.name)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const add = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.addDocument(mailboxId, { title, content })
      setTitle('')
      setContent('')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (doc) => {
    if (!window.confirm(`Delete document "${doc.title}"?`)) return
    try {
      await api.deleteDocument(doc.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="stack">
      <Alert>{error}</Alert>
      <div className="card">
        <h2>Reference documents</h2>
        <p className="muted">
          Extra context given to the agent with every email: FAQ, troubleshooting guides, product
          docs… Plain text or Markdown.
        </p>
        {docs.length === 0 ? (
          <p className="muted">No documents yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Size</th>
                <th>Added</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.title}</td>
                  <td className="muted">{doc.content.length.toLocaleString()} chars</td>
                  <td className="muted">{fmtDate(doc.created_at)}</td>
                  <td className="row-actions">
                    <button className="btn btn-small btn-danger" onClick={() => remove(doc)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <form className="card" onSubmit={add}>
        <h2>Add a document</h2>
        <div className="grid-2">
          <Field label="Title">
            <input required value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Import from file" hint=".txt / .md — loaded into the text area below">
            <input
              ref={fileInput}
              type="file"
              accept=".txt,.md,.markdown,text/plain"
              onChange={importFile}
            />
          </Field>
        </div>
        <Field label="Content">
          <textarea
            required
            rows={8}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </Field>
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Adding…' : 'Add document'}
          </button>
        </div>
      </form>
    </div>
  )
}
