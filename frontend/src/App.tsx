import { useCallback, useEffect, useState } from 'react'
import { api, type Card, type Profile } from './api'
import { CommandBox, OutreachList, ReviewCard } from './Outreach'
import { FactBank, ProfileForm, ResumeUpload } from './Setup'

type Tab = 'outreach' | 'setup'

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('outreach')
  const [items, setItems] = useState<Card[]>([])
  const [card, setCard] = useState<Card | null>(null)

  const refresh = useCallback(() => {
    api.profile().then(setProfile).catch(() => setError('Backend unreachable. Is it running on :8000?'))
    api.list().then(setItems).catch(() => {})
  }, [])

  useEffect(refresh, [refresh])

  function show(c: Card) {
    setCard(c)
    api.list().then(setItems)
  }

  async function deleteAll() {
    const typed = window.prompt('This deletes your resume, fact bank and all outreach. Type DELETE:')
    if (typed !== 'DELETE') return
    await api.deleteAll()
    setCard(null)
    refresh()
  }

  if (error) return <main><h1>Nobu</h1><p className="error">{error}</p></main>
  if (!profile) return <main><h1>Nobu</h1><p>Loading…</p></main>

  return (
    <main>
      <header className="row spread top">
        <h1>Nobu</h1>
        <span className={profile.dry_run ? 'badge' : 'badge live'}>
          {profile.dry_run ? 'Dry run: nothing is really sent' : 'LIVE sending'}
        </span>
      </header>

      {!profile.has_resume ? (
        <ResumeUpload onDone={refresh} />
      ) : (
        <>
          <nav className="row">
            <button className={tab === 'outreach' ? 'tab active' : 'tab'} onClick={() => setTab('outreach')}>
              Outreach
            </button>
            <button className={tab === 'setup' ? 'tab active' : 'tab'} onClick={() => setTab('setup')}>
              Profile & facts
            </button>
          </nav>

          {tab === 'outreach' ? (
            <div className="layout">
              <aside>
                <OutreachList
                  items={items}
                  selected={card?.id ?? null}
                  onSelect={(id) => api.get(id).then(setCard)}
                />
              </aside>
              <div>
                <CommandBox onCard={show} />
                {card && <ReviewCard key={card.id} card={card} onChange={show} />}
              </div>
            </div>
          ) : (
            <>
              <ProfileForm profile={profile} onSaved={setProfile} />
              <FactBank />
              <section className="panel">
                <h2>Danger zone</h2>
                <button className="danger" onClick={deleteAll}>
                  Delete all my data
                </button>
              </section>
            </>
          )}
        </>
      )}
    </main>
  )
}
