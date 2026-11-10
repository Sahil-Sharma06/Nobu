import { useEffect, useState } from 'react'
import { api, type Fact, type Profile } from './api'

const FACT_TYPES: Fact['type'][] = ['project', 'experience', 'achievement', 'skill', 'education']
const LINK_KEYS = ['github', 'portfolio', 'linkedin', 'resume']

export function ResumeUpload({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function upload(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      await api.uploadResume(file)
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <h2>1. Upload your resume</h2>
      <p className="muted">
        One time only. PDF, DOCX or TXT. It's saved in <code>data/</code> on this machine and turned
        into a fact bank you can edit. Nobu only ever claims things that are in it.
      </p>
      <input
        type="file"
        accept=".pdf,.docx,.txt"
        disabled={busy}
        onChange={(e) => upload(e.target.files?.[0])}
      />
      {busy && <p>Reading your resume…</p>}
      {error && <p className="error">{error}</p>}
    </section>
  )
}

export function ProfileForm({ profile, onSaved }: { profile: Profile; onSaved: (p: Profile) => void }) {
  const [p, setP] = useState(profile)
  const [saved, setSaved] = useState(false)

  async function save() {
    const { dry_run: _d, has_resume: _h, ...rest } = p
    const next = await api.saveProfile(rest)
    setP(next)
    onSaved(next)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  return (
    <section className="panel">
      <h2>Profile</h2>
      <div className="grid">
        <label>
          Name
          <input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} />
        </label>
        <label>
          Tone
          <input value={p.tone} onChange={(e) => setP({ ...p, tone: e.target.value })} />
        </label>
        <label>
          Daily cap
          <input
            type="number"
            min={0}
            max={50}
            value={p.daily_cap}
            onChange={(e) => setP({ ...p, daily_cap: Number(e.target.value) })}
          />
        </label>
        {LINK_KEYS.map((k) => (
          <label key={k}>
            {k}
            <input
              value={p.links[k] ?? ''}
              placeholder="https://…"
              onChange={(e) => setP({ ...p, links: { ...p.links, [k]: e.target.value } })}
            />
          </label>
        ))}
      </div>
      <label>
        Sign-off
        <textarea
          rows={2}
          value={p.sign_off}
          placeholder={'Thanks,\nYour name'}
          onChange={(e) => setP({ ...p, sign_off: e.target.value })}
        />
      </label>
      <button onClick={save}>{saved ? 'Saved' : 'Save profile'}</button>
    </section>
  )
}

function FactRow({ fact, onChange }: { fact: Fact; onChange: () => void }) {
  const [f, setF] = useState(fact)
  const dirty = JSON.stringify(f) !== JSON.stringify(fact)
  return (
    <li className="fact">
      <span className={`tag tag-${f.type}`}>{f.type}</span>
      <textarea
        rows={2}
        value={f.description}
        onChange={(e) => setF({ ...f, description: e.target.value })}
      />
      <input
        value={f.tech.join(', ')}
        placeholder="tech, comma separated"
        onChange={(e) =>
          setF({ ...f, tech: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })
        }
      />
      <input
        value={f.outcome}
        placeholder="outcome / numbers (only if true)"
        onChange={(e) => setF({ ...f, outcome: e.target.value })}
      />
      <div className="row">
        <span className="muted">#{f.id}</span>
        {dirty && (
          <button onClick={() => api.updateFact(f).then(onChange)}>Save</button>
        )}
        <button className="ghost" onClick={() => api.deleteFact(f.id).then(onChange)}>
          Delete
        </button>
      </div>
    </li>
  )
}

export function FactBank() {
  const [facts, setFacts] = useState<Fact[]>([])
  const [type, setType] = useState<Fact['type']>('project')
  const [desc, setDesc] = useState('')
  const load = () => api.facts().then(setFacts)
  useEffect(() => {
    load()
  }, [])

  async function add() {
    if (!desc.trim()) return
    await api.addFact({ type, description: desc, tech: [], outcome: '', links: [], tags: [] })
    setDesc('')
    load()
  }

  return (
    <section className="panel">
      <h2>Fact bank ({facts.length})</h2>
      <p className="muted">Everything Nobu says about you must come from here. Fix anything wrong.</p>
      <ul className="facts">
        {facts.map((f) => (
          <FactRow key={`${f.id}-${f.description}`} fact={f} onChange={load} />
        ))}
      </ul>
      <div className="row">
        <select value={type} onChange={(e) => setType(e.target.value as Fact['type'])}>
          {FACT_TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <input value={desc} placeholder="Add a fact…" onChange={(e) => setDesc(e.target.value)} />
        <button onClick={add}>Add</button>
      </div>
    </section>
  )
}
