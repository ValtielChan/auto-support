import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ModelSelect from '../components/ModelSelect.jsx'
import { Alert, Field, Spinner } from '../components/ui.jsx'

export default function Settings() {
  const [current, setCurrent] = useState(null)
  const [providers, setProviders] = useState([])
  const [form, setForm] = useState({
    provider: 'openai',
    openai_api_key: '',
    openai_base_url: '',
    default_model: '',
  })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  // Remount ModelSelect after a save so it refetches the model list.
  const [modelsKey, setModelsKey] = useState(0)

  useEffect(() => {
    Promise.all([api.getSettings(), api.getProviders()])
      .then(([s, p]) => {
        setCurrent(s)
        setProviders(p)
        setForm({
          provider: s.provider,
          openai_api_key: '',
          openai_base_url: s.openai_base_url,
          default_model: s.default_model,
        })
      })
      .catch((e) => setError(e.message))
  }, [])

  if (!current) return error ? <Alert>{error}</Alert> : <Spinner />

  const selectedProvider = providers.find((p) => p.id === form.provider)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const s = await api.saveSettings(form)
      setCurrent(s)
      setForm((f) => ({ ...f, openai_api_key: '', default_model: s.default_model }))
      setSaved(true)
      setModelsKey((k) => k + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Settings</h1>
      </div>
      <form onSubmit={submit} className="stack">
        <Alert>{error}</Alert>
        {saved && <Alert kind="success">Settings saved.</Alert>}
        <div className="card">
          <h2>LLM provider</h2>
          <div className="grid-2">
            <Field label="Provider">
              <select
                value={form.provider}
                onChange={(e) => {
                  const provider = e.target.value
                  const p = providers.find((x) => x.id === provider)
                  setForm((f) => ({ ...f, provider, default_model: p?.default_model || '' }))
                  setModelsKey((k) => k + 1)
                }}
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Default model" hint="Used unless an agent overrides it. Save after changing provider/key to refresh the list.">
              <ModelSelect
                key={modelsKey}
                value={form.default_model}
                onChange={(m) => setForm((f) => ({ ...f, default_model: m }))}
              />
            </Field>
          </div>
          <Field
            label="API key"
            hint={
              current.has_api_key
                ? `A key is configured (${current.api_key_hint}). Leave blank to keep it, type "-" to clear it.`
                : 'No key configured yet. Can also be provided via the OPENAI_API_KEY environment variable.'
            }
          >
            <input
              type="password"
              value={form.openai_api_key}
              onChange={(e) => setForm((f) => ({ ...f, openai_api_key: e.target.value }))}
              placeholder="sk-…"
            />
          </Field>
          {selectedProvider?.needs_base_url && (
            <Field
              label="Base URL"
              hint="The OpenAI-compatible endpoint, e.g. http://localhost:11434/v1 for Ollama, https://api.mistral.ai/v1 for Mistral. The model list is fetched live from this endpoint."
            >
              <input
                value={form.openai_base_url}
                onChange={(e) => setForm((f) => ({ ...f, openai_base_url: e.target.value }))}
                placeholder="https://…/v1"
              />
            </Field>
          )}
        </div>
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </>
  )
}
