const BASE = '/api'

export const getToken = () => localStorage.getItem('token')
export const setToken = (t) => localStorage.setItem('token', t)
export const clearToken = () => localStorage.removeItem('token')

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) {
    payload = new URLSearchParams(form)
  } else if (body !== undefined) {
    payload = JSON.stringify(body)
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(BASE + path, { method, headers, body: payload })
  if (res.status === 401 && path !== '/auth/login') {
    clearToken()
    window.location.assign('/login')
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json()).detail
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

const qs = (params) => {
  const clean = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  )
  const s = new URLSearchParams(clean).toString()
  return s ? `?${s}` : ''
}

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', form: { username, password } }),
  me: () => request('/auth/me'),

  listMailboxes: () => request('/mailboxes'),
  getMailbox: (id) => request(`/mailboxes/${id}`),
  createMailbox: (data) => request('/mailboxes', { method: 'POST', body: data }),
  updateMailbox: (id, data) => request(`/mailboxes/${id}`, { method: 'PUT', body: data }),
  deleteMailbox: (id) => request(`/mailboxes/${id}`, { method: 'DELETE' }),
  testMailboxPayload: (data) => request('/mailboxes/test', { method: 'POST', body: data }),
  testMailbox: (id) => request(`/mailboxes/${id}/test`, { method: 'POST' }),
  runMailbox: (id) => request(`/mailboxes/${id}/run`, { method: 'POST' }),

  getAgent: (mailboxId) => request(`/mailboxes/${mailboxId}/agent`),
  saveAgent: (mailboxId, data) =>
    request(`/mailboxes/${mailboxId}/agent`, { method: 'PUT', body: data }),

  listDocuments: (mailboxId) => request(`/mailboxes/${mailboxId}/agent/documents`),
  addDocument: (mailboxId, data) =>
    request(`/mailboxes/${mailboxId}/agent/documents`, { method: 'POST', body: data }),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),

  listKnowledge: (mailboxId, kind) =>
    request(`/mailboxes/${mailboxId}/agent/knowledge${qs({ kind })}`),
  addKnowledge: (mailboxId, data) =>
    request(`/mailboxes/${mailboxId}/agent/knowledge`, { method: 'POST', body: data }),
  updateKnowledge: (id, data) => request(`/knowledge/${id}`, { method: 'PUT', body: data }),
  deleteKnowledge: (id) => request(`/knowledge/${id}`, { method: 'DELETE' }),

  listInbox: (mailboxId, limit = 50) =>
    request(`/mailboxes/${mailboxId}/inbox${qs({ limit })}`),
  getInboxMessage: (mailboxId, uid) => request(`/mailboxes/${mailboxId}/inbox/${uid}`),
  setInboxFlags: (mailboxId, uids, seen) =>
    request(`/mailboxes/${mailboxId}/inbox/flags`, { method: 'POST', body: { uids, seen } }),
  deleteInboxMessages: (mailboxId, uids) =>
    request(`/mailboxes/${mailboxId}/inbox/delete`, { method: 'POST', body: { uids } }),
  replyInboxMessage: (mailboxId, uid, body) =>
    request(`/mailboxes/${mailboxId}/inbox/${uid}/reply`, { method: 'POST', body: { body } }),
  suggestReply: (mailboxId, uid, instruction) =>
    request(`/mailboxes/${mailboxId}/inbox/${uid}/suggest`, {
      method: 'POST',
      body: { instruction },
    }),

  listEmails: (params) => request(`/emails${qs(params)}`),
  getEmail: (id) => request(`/emails/${id}`),

  listReplies: (status = 'draft', mailbox_id) => request(`/replies${qs({ status, mailbox_id })}`),
  updateReply: (id, body) => request(`/replies/${id}`, { method: 'PUT', body: { body } }),
  approveReply: (id) => request(`/replies/${id}/approve`, { method: 'POST' }),
  rejectReply: (id) => request(`/replies/${id}/reject`, { method: 'POST' }),

  listRuns: (params) => request(`/runs${qs(params)}`),

  getSettings: () => request('/settings'),
  saveSettings: (data) => request('/settings', { method: 'PUT', body: data }),
  getProviders: () => request('/providers'),
  getModels: () => request('/models'),

  assistantChat: (mailboxId, messages) =>
    request(`/mailboxes/${mailboxId}/assistant`, { method: 'POST', body: { messages } }),

  stats: () => request('/dashboard/stats'),
}

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString() : '-')
