import { useState } from 'react'
import { Alert, Badge, Field, Spinner } from '../components/ui.jsx'

const COLORS = [
  ['Green - primary', '--green', '#2EE88A'],
  ['Green dark', '--green-dark', '#12C96B'],
  ['Green pale', '--green-pale', '#C9F9E0'],
  ['Pink - secondary', '--pink', '#FF90E8'],
  ['Pink dark', '--pink-dark', '#F556CF'],
  ['Pink pale', '--pink-pale', '#FFD9F6'],
  ['Black', '--black', '#111111'],
  ['White', '--white', '#FFFFFF'],
  ['Background', '--bg', '#ECECEA'],
  ['Gray', '--gray', '#D8D8D4'],
  ['Muted', '--muted', '#4A4A46'],
]

const BADGES = [
  'new',
  'awaiting_approval',
  'replied',
  'escalated',
  'ignored',
  'error',
  'draft',
  'sent',
  'rejected',
  'running',
  'success',
  'support',
  'partnership',
  'marketing',
  'spam',
  'other',
]

export default function DesignSystem() {
  const [tab, setTab] = useState('One')
  const [radio, setRadio] = useState('a')

  return (
    <>
      <div className="page-head">
        <h1>Design system</h1>
      </div>

      <div className="card">
        <h2><span className="hl">Colors</span></h2>
        <p className="muted">
          Two colors only: green (primary) and pink (secondary), each with a dark and pale
          variant. Everything else is neutral - black, white, background, gray.
        </p>
        <div className="swatches">
          {COLORS.map(([label, varName, hex]) => (
            <div className="swatch" key={varName}>
              <div className="swatch-color" style={{ background: `var(${varName})` }} />
              <div className="swatch-label">
                {label}
                <small>{varName} · {hex}</small>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Typography</span></h2>
        <h1>Heading one</h1>
        <h1 className="ul-pink" style={{ marginTop: '0.5rem' }}>Underlined h1</h1>
        <h2 style={{ marginTop: '1rem' }}>Heading two</h2>
        <h3>Heading three</h3>
        <p>
          Body text in Space Grotesk. Headings use Archivo Black, uppercase. You can{' '}
          <span className="hl">highlight in green</span>,{' '}
          <span className="hl-pink">highlight in pink</span>, use a{' '}
          <span className="ul-green">green underline</span> or a{' '}
          <span className="ul-pink">pink underline</span>, and links look{' '}
          <a href="#top">like this</a>.
        </p>
        <p className="muted">Muted paragraph for hints and secondary information.</p>
      </div>

      <div className="card">
        <h2><span className="hl">Buttons</span></h2>
        <div className="demo-row">
          <button className="btn btn-primary">Primary</button>
          <button className="btn">Default</button>
          <button className="btn btn-danger">Danger</button>
          <button className="btn btn-ghost">Ghost</button>
          <button className="btn" disabled>Disabled</button>
        </div>
        <div className="demo-row">
          <button className="btn btn-small btn-primary">Small primary</button>
          <button className="btn btn-small">Small</button>
          <button className="btn btn-small btn-danger">Small danger</button>
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Forms</span></h2>
        <div className="grid-2">
          <Field label="Text input" hint="With a hint underneath">
            <input placeholder="Type something…" />
          </Field>
          <Field label="Password">
            <input type="password" defaultValue="secret" />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Select">
            <select defaultValue="b">
              <option value="a">Option A</option>
              <option value="b">Option B</option>
              <option value="c">Option C</option>
            </select>
          </Field>
          <Field label="File input">
            <input type="file" />
          </Field>
        </div>
        <Field label="Textarea">
          <textarea rows={3} placeholder="Multi-line text…" />
        </Field>
        <label className="checkbox">
          <input type="checkbox" defaultChecked /> <strong>Checkbox</strong> - checked by default
        </label>
        <label className="checkbox">
          <input type="checkbox" /> Unchecked checkbox
        </label>
        <div className="demo-row">
          {['a', 'b', 'c'].map((v) => (
            <label className="checkbox" key={v} style={{ margin: 0 }}>
              <input
                type="radio"
                name="demo-radio"
                checked={radio === v}
                onChange={() => setRadio(v)}
              />
              Radio {v.toUpperCase()}
            </label>
          ))}
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Icons</span></h2>
        <p className="muted">
          Font Awesome (free, solid set), bundled locally. Use{' '}
          <code>{'<i className="fa-solid fa-…" />'}</code> - with <code>fa-fw</code> for
          fixed-width alignment in menus.
        </p>
        <div className="demo-row" style={{ fontSize: '1.3rem', gap: '1.1rem' }}>
          {[
            'fa-gauge-high',
            'fa-envelope',
            'fa-list-check',
            'fa-gear',
            'fa-palette',
            'fa-robot',
            'fa-file-lines',
            'fa-clock-rotate-left',
            'fa-wand-magic-sparkles',
            'fa-paper-plane',
            'fa-plus',
            'fa-pen',
            'fa-trash',
            'fa-plug',
            'fa-floppy-disk',
            'fa-play',
            'fa-xmark',
            'fa-right-from-bracket',
          ].map((icon) => (
            <i key={icon} className={`fa-solid ${icon}`} title={icon} />
          ))}
        </div>
        <div className="demo-row">
          <button className="btn btn-primary"><i className="fa-solid fa-play" /> With icon</button>
          <button className="btn"><i className="fa-solid fa-plug" /> Test</button>
          <button className="btn btn-danger"><i className="fa-solid fa-trash" /> Delete</button>
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Badges</span></h2>
        <div className="demo-row">
          {BADGES.map((b) => (
            <Badge key={b} value={b} />
          ))}
          <Badge value={null} />
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Alerts</span></h2>
        <Alert>Something went wrong - this is the error alert.</Alert>
        <Alert kind="success">All good - this is the success alert.</Alert>
      </div>

      <div className="card">
        <h2><span className="hl">Tabs</span></h2>
        <div className="tabs" style={{ marginBottom: 0 }}>
          {['One', 'Two', 'Three'].map((t) => (
            <button
              key={t}
              className={`tab ${tab === t ? 'tab-active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <h2 style={{ margin: '0 0 0.85rem' }}><span className="hl-pink">Tiles</span></h2>
      <div className="tiles">
        <div className="tile">
          <div className="tile-value">42</div>
          <div className="tile-label">Standard tile</div>
        </div>
        <div className="tile tile-highlight">
          <div className="tile-value">7</div>
          <div className="tile-label">Highlighted tile</div>
        </div>
        <a className="tile-link" href="#top">
          <div className="tile">
            <div className="tile-value">3</div>
            <div className="tile-label">Clickable tile</div>
          </div>
        </a>
      </div>

      <div className="card">
        <h2><span className="hl">Table</span></h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Category</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr className="clickable">
              <td>Hoverable row</td>
              <td><Badge value="replied" /></td>
              <td><Badge value="support" /></td>
              <td className="row-actions">
                <button className="btn btn-small">Edit</button>
                <button className="btn btn-small btn-danger">Delete</button>
              </td>
            </tr>
            <tr className="clickable">
              <td>Another row</td>
              <td><Badge value="awaiting_approval" /></td>
              <td><Badge value="partnership" /></td>
              <td className="row-actions">
                <button className="btn btn-small">Edit</button>
                <button className="btn btn-small btn-danger">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div className="pager">
          <button className="btn btn-small">← Prev</button>
          <span className="muted">Page 1 / 3</span>
          <button className="btn btn-small">Next →</button>
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Content blocks</span></h2>
        <pre className="email-body">{'From: customer@example.com\nSubject: Help!\n\nA preformatted email body block, scrollable when long.'}</pre>
        <div className="reply-block">
          <div className="muted">
            Reply <Badge value="draft" /> · gpt-5.6-terra
          </div>
          <pre className="email-body">{'Hi,\n\nThanks for reaching out - here is the reply body.\n\nBest,\nSupport team'}</pre>
        </div>
      </div>

      <div className="card empty">
        <p>Empty state card. 🎉</p>
        <p className="muted">Used when a list has nothing to show yet.</p>
      </div>

      <div className="card">
        <h2><span className="hl">Copilot</span></h2>
        <div className="assistant-demo demo-row" style={{ alignItems: 'flex-start' }}>
          <button className="assistant-fab" type="button">
            <i className="fa-solid fa-wand-magic-sparkles" /> Copilot
          </button>
          <div className="assistant-panel">
            <div className="assistant-head">
              <span>
                <i className="fa-solid fa-wand-magic-sparkles" /> Configuration copilot
              </span>
              <div>
                <button className="btn btn-small" type="button">Clear</button>
                <button className="btn btn-small" type="button">✕</button>
              </div>
            </div>
            <div className="assistant-messages">
              <div className="msg msg-assistant">Hi! Describe your product and I’ll write the context for you.</div>
              <div className="msg msg-user">My product is a todo app for teams.</div>
              <div className="msg msg-assistant">
                Done - I wrote a full product context.
                <div className="msg-actions">
                  <span className="badge badge-success">✓ Agent configuration updated</span>
                </div>
              </div>
              <div className="msg msg-assistant msg-error">⚠ Error message bubble.</div>
              <div className="msg msg-assistant msg-typing">Working…</div>
            </div>
            <div className="assistant-input">
              <textarea rows={2} placeholder="Message…" readOnly />
              <button className="btn btn-primary" type="button">Send</button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2><span className="hl">Spinner</span></h2>
        <Spinner />
      </div>
    </>
  )
}
