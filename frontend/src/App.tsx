import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState('checking…')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json() as Promise<{ status: string }>)
      .then((d) => setStatus(d.status))
      .catch(() => setStatus('backend unreachable'))
  }, [])

  return (
    <main>
      <h1>Nobu</h1>
      <p>Backend: {status}</p>
    </main>
  )
}
