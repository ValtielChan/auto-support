import { Link } from 'react-router-dom'
import TopBar from './TopBar.jsx'

export default function SimpleLayout({ children, back = true }) {
  return (
    <div className="simple-shell">
      <TopBar />
      <div className="simple-main">
        <div className="page-narrow">
          {back && (
            <Link to="/" className="btn btn-small backlink">
              <i className="fa-solid fa-arrow-left" /> All mailboxes
            </Link>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}
