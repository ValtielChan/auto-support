import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { getToken } from './api.js'
import SimpleLayout from './components/SimpleLayout.jsx'
import Brand from './pages/Brand.jsx'
import DesignSystem from './pages/DesignSystem.jsx'
import Home from './pages/Home.jsx'
import Login from './pages/Login.jsx'
import MailboxForm from './pages/MailboxForm.jsx'
import Settings from './pages/Settings.jsx'

function RequireAuth({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/m/:id" element={<Brand />} />
              <Route path="/m/:id/edit" element={<SimpleLayout><MailboxForm /></SimpleLayout>} />
              <Route path="/mailboxes/new" element={<SimpleLayout><MailboxForm /></SimpleLayout>} />
              <Route path="/settings" element={<SimpleLayout><Settings /></SimpleLayout>} />
              <Route path="/design" element={<SimpleLayout><DesignSystem /></SimpleLayout>} />
              {/* legacy paths */}
              <Route path="/mailboxes/:id" element={<LegacyMailboxRedirect />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </RequireAuth>
        }
      />
    </Routes>
  )
}

// Old bookmarks pointed at /mailboxes/:id - send them to the new /m/:id.
function LegacyMailboxRedirect() {
  const { id } = useParams()
  return <Navigate to={`/m/${id}`} replace />
}
