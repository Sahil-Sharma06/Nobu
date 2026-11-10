import { useState } from 'react'
import { api, ApiError, type Card, type Parsed } from './api'

const FIELDS: [keyof Parsed, string][] = [
  ['company', 'Company'],
  ['role', 'Role'],
  ['company_domain', 'Domain'],
  ['job_url', 'Job URL'],
  ['contact_name', 'Contact name'],
  ['contact_email', 'Contact email'],
]

function errText(e: unknown): string {
  if (e instanceof ApiError && e.problems.length) return e.problems.join(' ')
  return (e as Error).message
}

export function CommandBox({ onCard }: { onCard: (c: Card) => void }) {
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<Parsed | null>(null)
  const [issues, setIssues] = useState<string[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  async function runPipeline(p: Parsed) {
    setBusy('Researching, matching, drafting… (this can take a minute)')
    try {
      onCard(await api.run(p))
      setParsed(null)
      setText('')
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy('')
    }
  }

  async function submit() {
    if (!text.trim()) return
    setError('')
    setBusy('Understanding your command…')
    try {
      const r = await api.parse(text)
      setBusy('')
      if (r.issues.length === 0) {
        await runPipeline(r.parsed)
      } else {
        setParsed(r.parsed)
        setIssues(r.issues)
      }
    } catch (e) {
      setBusy('')
      setError(errText(e))
    }
  }

  return (
    <section className="panel">
      <h2>New outreach</h2>
      <div className="row">
        <input
          className="command"
          value={text}
          placeholder="Reach out to Acme (acme.dev) for the backend intern role"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          disabled={!!busy}
        />
        <button onClick={submit} disabled={!!busy}>
          Go
        </button>
      </div>
      {parsed && (
        <div className="confirm">
          <p>
            <strong>Please check before I spend any research:</strong>
          </p>
          <ul>
            {issues.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
          <div className="grid">
            {FIELDS.map(([k, label]) => (
              <label key={k}>
                {label}
                <input
                  value={parsed[k]}
                  onChange={(e) => setParsed({ ...parsed, [k]: e.target.value })}
                />
              </label>
            ))}
          </div>
          <button onClick={() => runPipeline(parsed)} disabled={!!busy}>
            Looks right, continue
          </button>
          <button className="ghost" onClick={() => setParsed(null)}>
            Cancel
          </button>
        </div>
      )}
      {busy && <p className="muted">{busy}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function ReviewCard({ card, onChange }: { card: Card; onChange: (c: Card) => void }) {
  const [subject, setSubject] = useState(card.subject)
  const [body, setBody] = useState(card.body ?? '')
  const [instructions, setInstructions] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactName, setContactName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const editable = card.state === 'drafted' || card.state === 'approved'
  const dirty = subject !== card.subject || body !== card.body

  async function act(fn: () => Promise<Card>) {
    setBusy(true)
    setError('')
    try {
      const next = await fn()
      setSubject(next.subject)
      setBody(next.body ?? '')
      onChange(next)
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  function readAloud() {
    speechSynthesis.cancel()
    speechSynthesis.speak(new SpeechSynthesisUtterance(`Subject: ${subject}. ${body}`))
  }

  function sendWithConfirm() {
    const to = card.contact?.email ?? '(nobody)'
    const mode = card.dry_run ? 'DRY RUN (nothing leaves your machine)' : 'REAL SEND'
    if (window.confirm(`${mode}\n\nTo: ${to}\nSubject: ${subject}\n\nSend it?`)) {
      act(() => api.send(card.id))
    }
  }

  const open = (card.flags ?? []).filter((f) => !f.resolved)

  return (
    <section className="panel card">
      <header className="row spread">
        <h2>
          {card.company?.name} · {card.role}
        </h2>
        <span className={`state state-${card.state}`}>{card.state}</span>
      </header>

      <div className="contact">
        <h3>Recipient</h3>
        {card.contact ? (
          <p>
            <strong>{card.contact.name || card.contact.email}</strong> &lt;{card.contact.email}&gt; ·
            confidence {Math.round(card.contact.confidence * 100)}% · from{' '}
            {card.contact.source.startsWith('http') ? (
              <a href={card.contact.source} target="_blank" rel="noreferrer">
                {card.contact.source}
              </a>
            ) : (
              card.contact.source
            )}
          </p>
        ) : (
          <p className="error">No recipient found.</p>
        )}
        <p className="muted">{card.contact_rationale}</p>
        {editable && (
          <div className="row">
            <input
              placeholder="name"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
            />
            <input
              placeholder="email you know is right"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
            />
            <button
              className="ghost"
              disabled={!contactEmail || busy}
              onClick={() => act(() => api.setContact(card.id, contactEmail, contactName))}
            >
              Use this contact
            </button>
          </div>
        )}
      </div>

      <div>
        <h3>Why these facts</h3>
        <ul>
          {(card.highlighted ?? []).map((h) => (
            <li key={h.fact_id}>
              <strong>#{h.fact_id}</strong> {h.description}
              <br />
              <span className="muted">→ {h.rationale}</span>
            </li>
          ))}
        </ul>
      </div>

      <label>
        Subject
        <input value={subject} disabled={!editable} onChange={(e) => setSubject(e.target.value)} />
      </label>
      <label>
        Body
        <textarea
          rows={14}
          value={body}
          disabled={!editable}
          onChange={(e) => setBody(e.target.value)}
        />
      </label>

      {(card.flags ?? []).length > 0 && (
        <div className="flags">
          <h3>Critic flags ({open.length} open)</h3>
          <ul>
            {(card.flags ?? []).map((f) => (
              <li key={f.index} className={f.resolved ? 'resolved' : ''}>
                <code>{f.code}</code> {f.message}
                {!f.resolved && editable && f.code !== 'no_contact' && (
                  <button className="ghost" onClick={() => act(() => api.resolveFlag(card.id, f.index))}>
                    It's fine, resolve
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {editable && (
        <div className="row actions">
          {dirty && (
            <button disabled={busy} onClick={() => act(() => api.edit(card.id, subject, body))}>
              Save edit & re-check
            </button>
          )}
          <input
            placeholder="e.g. make it shorter, mention my hackathon win"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
          <button
            className="ghost"
            disabled={busy}
            onClick={() => act(() => api.regenerate(card.id, instructions))}
          >
            Regenerate
          </button>
        </div>
      )}

      <div className="row actions">
        <button className="ghost" onClick={readAloud}>
          Read it to me
        </button>
        {card.state === 'drafted' && (
          <button disabled={busy || dirty || open.length > 0} onClick={() => act(() => api.approve(card.id))}>
            Approve
          </button>
        )}
        {card.state === 'approved' && (
          <button disabled={busy || dirty} onClick={sendWithConfirm}>
            {card.dry_run ? 'Send (dry run)' : 'Send'}
          </button>
        )}
        {editable && (
          <button className="danger" disabled={busy} onClick={() => act(() => api.discard(card.id))}>
            Discard
          </button>
        )}
      </div>

      {card.state === 'approved' && (card.send_problems ?? []).length > 0 && (
        <ul className="error">
          {card.send_problems!.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {error && <p className="error">{error}</p>}

      <details>
        <summary>Sources ({(card.sources ?? []).length})</summary>
        <ul>
          {(card.sources ?? []).map((s) => (
            <li key={s}>
              <a href={s} target="_blank" rel="noreferrer">
                {s}
              </a>
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}

export function OutreachList({
  items,
  selected,
  onSelect,
}: {
  items: Card[]
  selected: number | null
  onSelect: (id: number) => void
}) {
  if (items.length === 0) return <p className="muted">No outreach yet.</p>
  return (
    <ul className="list">
      {items.map((c) => (
        <li key={c.id}>
          <button className={c.id === selected ? 'item active' : 'item'} onClick={() => onSelect(c.id)}>
            <span>
              {c.company?.name} · {c.role}
            </span>
            <span className={`state state-${c.state}`}>{c.state}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
