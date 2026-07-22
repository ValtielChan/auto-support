import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import AgentTab from '../components/AgentTab.jsx'
import ApprovalsTab from '../components/ApprovalsTab.jsx'
import AssistantPanel from '../components/AssistantPanel.jsx'
import DocumentsTab from '../components/DocumentsTab.jsx'
import InboxTab from '../components/InboxTab.jsx'
import KnowledgeTab from '../components/KnowledgeTab.jsx'
import RunsTab from '../components/RunsTab.jsx'
import TopBar from '../components/TopBar.jsx'
import { Alert, Spinner } from '../components/ui.jsx'

const SECTIONS = [
  ['inbox', 'Inbox', 'fa-inbox'],
  ['agent', 'Agent', 'fa-robot'],
  ['knowledge', 'Knowledge', 'fa-book'],
  ['documents', 'Documents', 'fa-file-lines'],
  ['approvals', 'Approvals', 'fa-list-check'],
  ['runs', 'Runs', 'fa-clock-rotate-left'],
]

export default function Brand() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [mailbox, setMailbox] = useState(null)
  const [mailboxes, setMailboxes] = useState([])
  const [section, setSection] = useState('inbox')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    setMailbox(null)
    setSection('inbox')
    setNotice('')
    api.getMailbox(id).then(setMailbox).catch((e) => setError(e.message))
    api.listMailboxes().then(setMailboxes).catch(() => {})
  }, [id])

  const runNow = async () => {
    setNotice('')
    setError('')
    try {
      await api.runMailbox(id)
      setNotice('Run started — check Runs in a moment.')
    } catch (e) {
      setError(e.message)
    }
  }

  if (!mailbox) {
    return (
      <div className="brand-shell">
        <TopBar />
        <div className="brand-body">{error ? <Alert>{error}</Alert> : <Spinner />}</div>
      </div>
    )
  }

  return (
    <div className="brand-shell">
      <TopBar mailboxes={mailboxes} currentId={mailbox.id} />
      <div className="brand-body">
        <nav className="brand-sidebar">
          <div className="brand-name" title={mailbox.email_address}>
            <div className="brand-name-title">{mailbox.name}</div>
            <div className="muted brand-name-addr">{mailbox.email_address}</div>
          </div>
          {SECTIONS.map(([key, label, icon]) => (
            <button
              key={key}
              className={`brand-navlink ${section === key ? 'active' : ''}`}
              onClick={() => setSection(key)}
            >
              <i className={`fa-solid fa-fw ${icon}`} /> {label}
            </button>
          ))}
          <div className="brand-sidebar-foot">
            <button className="btn btn-small btn-primary" onClick={runNow}>
              <i className="fa-solid fa-play" /> Run agent now
            </button>
            <button className="btn btn-small" onClick={() => navigate(`/m/${id}/edit`)}>
              <i className="fa-solid fa-pen" /> Edit connection
            </button>
          </div>
        </nav>

        <main className="brand-main">
          {(error || notice) && (
            <div className="brand-notice">
              <Alert>{error}</Alert>
              {notice && <Alert kind="success">{notice}</Alert>}
            </div>
          )}
          {section === 'inbox' ? (
            <InboxTab key={refreshKey} mailboxId={id} />
          ) : (
            <div className="brand-scroll">
              {section === 'agent' && <AgentTab key={refreshKey} mailboxId={id} />}
              {section === 'knowledge' && <KnowledgeTab key={refreshKey} mailboxId={id} />}
              {section === 'documents' && <DocumentsTab key={refreshKey} mailboxId={id} />}
              {section === 'approvals' && <ApprovalsTab key={refreshKey} mailboxId={id} />}
              {section === 'runs' && <RunsTab mailboxId={id} />}
            </div>
          )}
        </main>
      </div>

      <AssistantPanel
        mailboxId={id}
        onChanged={() => {
          setRefreshKey((k) => k + 1)
          api.getMailbox(id).then(setMailbox).catch(() => {})
        }}
      />
    </div>
  )
}
