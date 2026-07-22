import { useEffect } from 'react'

const STATUS_LABELS = {
  new: 'New',
  awaiting_approval: 'Awaiting approval',
  replied: 'Replied',
  escalated: 'Escalated',
  ignored: 'Ignored',
  error: 'Error',
  draft: 'Draft',
  sent: 'Sent',
  rejected: 'Rejected',
  running: 'Running',
  success: 'Success',
}

export function Badge({ value }) {
  if (!value) return <span className="badge badge-muted">-</span>
  return (
    <span className={`badge badge-${value}`}>{STATUS_LABELS[value] || value}</span>
  )
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null
  return <div className={`alert alert-${kind}`}>{children}</div>
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function Spinner() {
  return <div className="spinner" aria-label="Loading" />
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn btn-small" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
