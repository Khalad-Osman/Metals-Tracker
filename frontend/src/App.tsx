import { useEffect, useState } from 'react'

// Where the FastAPI backend runs during development.
const API_URL = 'http://localhost:8000'

type Status = 'checking' | 'ok' | 'unreachable'

function App() {
  const [status, setStatus] = useState<Status>('checking')

  // On page load, ask the backend's /health endpoint whether it's running.
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => response.json())
      .then((data) => setStatus(data.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main>
      <h1>Metals Tracker</h1>
      <p>
        Backend: <strong className={`status-${status}`}>{status}</strong>
      </p>
    </main>
  )
}

export default App
