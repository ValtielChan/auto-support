import { useEffect, useState } from 'react'
import { api } from '../api.js'

/**
 * Model picker fed by GET /api/models (curated list for OpenAI, live list for
 * compatible endpoints). Falls back to a free-text input when no list is
 * available (e.g. custom endpoint that doesn't serve /models).
 */
export default function ModelSelect({ value, onChange, defaultLabel = null }) {
  const [models, setModels] = useState(null)

  useEffect(() => {
    api
      .getModels()
      .then((r) => setModels(r.models))
      .catch(() => setModels([]))
  }, [])

  if (models === null) {
    return <select disabled><option>Loading models…</option></select>
  }

  if (models.length === 0) {
    return (
      <input
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={defaultLabel || 'model id'}
      />
    )
  }

  const options = models.includes(value) || !value ? models : [value, ...models]

  return (
    <select value={value || ''} onChange={(e) => onChange(e.target.value)}>
      {defaultLabel && <option value="">{defaultLabel}</option>}
      {options.map((m) => (
        <option key={m} value={m}>
          {m}
        </option>
      ))}
    </select>
  )
}
