import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { clearToken } from '../api.js'

export default function TopBar({ mailboxes, currentId }) {
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const logout = () => {
    clearToken()
    navigate('/login')
  }

  const hasSwitcher = mailboxes && mailboxes.length > 0 && currentId != null

  return (
    <header className="topbar">
      <div className="topbar-left">
        <NavLink to="/" className="brand">
          <img src="/logo.svg" className="brand-logo" alt="" /> Auto&nbsp;<span className="hl">Support</span>
        </NavLink>
        {hasSwitcher && (
          <select
            className="brand-switch"
            value={currentId}
            onChange={(e) => navigate(`/m/${e.target.value}`)}
            aria-label="Switch mailbox"
          >
            {mailboxes.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="topbar-right" ref={ref}>
        <button className="btn profile-btn" onClick={() => setMenuOpen((o) => !o)}>
          <i className="fa-solid fa-user" /> Menu <i className="fa-solid fa-chevron-down" />
        </button>
        {menuOpen && (
          <div className="profile-menu">
            <NavLink to="/" onClick={() => setMenuOpen(false)}>
              <i className="fa-solid fa-fw fa-grip" /> All mailboxes
            </NavLink>
            <NavLink to="/settings" onClick={() => setMenuOpen(false)}>
              <i className="fa-solid fa-fw fa-gear" /> Settings
            </NavLink>
            <NavLink to="/design" onClick={() => setMenuOpen(false)}>
              <i className="fa-solid fa-fw fa-palette" /> Design system
            </NavLink>
            <button onClick={logout}>
              <i className="fa-solid fa-fw fa-right-from-bracket" /> Log out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
