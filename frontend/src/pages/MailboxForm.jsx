import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { Alert, Field, Spinner } from '../components/ui.jsx'

const EMPTY = {
  name: '',
  email_address: '',
  imap_host: '',
  imap_port: 993,
  imap_ssl: true,
  imap_username: '',
  imap_password: '',
  imap_folder: 'INBOX',
  smtp_host: '',
  smtp_port: 587,
  smtp_tls: true,
  smtp_username: '',
  smtp_password: '',
  active: true,
}

export default function MailboxForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const [form, setForm] = useState(isEdit ? null : EMPTY)
  const [error, setError] = useState('')
  const [test, setTest] = useState(null)
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (isEdit) {
      api
        .getMailbox(id)
        .then((mb) => setForm({ ...EMPTY, ...mb, imap_password: '', smtp_password: '' }))
        .catch((e) => setError(e.message))
    }
  }, [id, isEdit])

  if (!form) return error ? <Alert>{error}</Alert> : <Spinner />

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [key]: value }))
  }
  const setNum = (key) => (e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) || 0 }))

  const runTest = async () => {
    setBusy('test')
    setError('')
    setTest(null)
    try {
      // For an existing mailbox with untouched passwords, test the saved ones.
      const result =
        isEdit && !form.imap_password && !form.smtp_password
          ? await api.testMailbox(id)
          : await api.testMailboxPayload(form)
      setTest(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy('save')
    setError('')
    try {
      if (isEdit) {
        await api.updateMailbox(id, form)
        navigate(`/m/${id}`)
      } else {
        const mb = await api.createMailbox(form)
        navigate(`/m/${mb.id}`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const pwdHint = isEdit ? 'Leave blank to keep the stored password' : undefined

  return (
    <>
      <div className="page-head">
        <h1>{isEdit ? 'Edit mailbox' : 'Add mailbox'}</h1>
      </div>
      <form onSubmit={submit} className="stack">
        <Alert>{error}</Alert>
        {test && (
          <Alert kind={test.imap_ok && test.smtp_ok ? 'success' : 'error'}>
            <div>IMAP: {test.imap_ok ? '✓' : '✗'} {test.imap_detail}</div>
            <div>SMTP: {test.smtp_ok ? '✓' : '✗'} {test.smtp_detail}</div>
          </Alert>
        )}

        <div className="card">
          <h2>General</h2>
          <div className="grid-2">
            <Field label="Display name">
              <input required value={form.name} onChange={set('name')} placeholder="Support — MyProduct" />
            </Field>
            <Field label="Email address">
              <input required type="email" value={form.email_address} onChange={set('email_address')} placeholder="support@myproduct.com" />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={form.active} onChange={set('active')} /> Mailbox active
          </label>
        </div>

        <div className="card">
          <h2>IMAP (incoming)</h2>
          <div className="grid-3">
            <Field label="Host">
              <input required value={form.imap_host} onChange={set('imap_host')} placeholder="imap.example.com" />
            </Field>
            <Field label="Port">
              <input required type="number" value={form.imap_port} onChange={setNum('imap_port')} />
            </Field>
            <Field label="Folder">
              <input value={form.imap_folder} onChange={set('imap_folder')} />
            </Field>
          </div>
          <div className="grid-2">
            <Field label="Username">
              <input required value={form.imap_username} onChange={set('imap_username')} />
            </Field>
            <Field label="Password" hint={pwdHint}>
              <input type="password" required={!isEdit} value={form.imap_password} onChange={set('imap_password')} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={form.imap_ssl} onChange={set('imap_ssl')} /> Use SSL (port 993)
          </label>
        </div>

        <div className="card">
          <h2>SMTP (outgoing)</h2>
          <div className="grid-2">
            <Field label="Host">
              <input required value={form.smtp_host} onChange={set('smtp_host')} placeholder="smtp.example.com" />
            </Field>
            <Field label="Port">
              <input required type="number" value={form.smtp_port} onChange={setNum('smtp_port')} />
            </Field>
          </div>
          <div className="grid-2">
            <Field label="Username">
              <input required value={form.smtp_username} onChange={set('smtp_username')} />
            </Field>
            <Field label="Password" hint={pwdHint}>
              <input type="password" required={!isEdit} value={form.smtp_password} onChange={set('smtp_password')} />
            </Field>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={form.smtp_tls} onChange={set('smtp_tls')} /> Use STARTTLS (ignored on port 465, which uses implicit SSL)
          </label>
        </div>

        <div className="actions">
          <button type="button" className="btn" onClick={runTest} disabled={busy !== ''}>
            <i className="fa-solid fa-plug" /> {busy === 'test' ? 'Testing…' : 'Test connection'}
          </button>
          <button className="btn btn-primary" disabled={busy !== ''}>
            <i className="fa-solid fa-floppy-disk" /> {busy === 'save' ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </>
  )
}
