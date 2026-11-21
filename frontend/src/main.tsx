import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Item = { slug: string; title: string; url: string; minutes: number; reason: string; topic: string; difficulty: string; kind: string }
type Plan = { day: string; minutes: number; source: 'ai' | 'rules'; items: Item[] }
type Profile = { username: string; counts: Record<string, number>; counts_available: boolean; recent_available: boolean; synced_at: string }
type Note = { slug: string; title: string; topic: string; day: string; performance: string; hints: number | null; concepts: string[]; mistake: string | null; takeaway: string | null }
type Dashboard = {
  plan: Plan | null
  profile: Profile | null
  ai_enabled: boolean
  notes: Note[]
  weak_concepts: { name: string; count: number }[]
  reviews: { slug: string; title: string; due: string }[]
  progress: { plans: number; sessions: number; synced_problems: number; due: number }
}
type Action = 'plans' | 'profile' | 'sessions'

function localDay() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const date = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${date}`
}

function displayDay(day: string) {
  return new Date(day + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

async function api<T>(path: string, payload?: object): Promise<T> {
  const response = await fetch('/api/' + path, payload && {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(typeof error?.detail === 'string' ? error.detail : 'Request failed. Try again.')
  }
  return response.json()
}

function loadDashboard() {
  return api<Dashboard>('dashboard?day=' + localDay())
}

function App() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [minutes, setMinutes] = useState(45)
  const [username, setUsername] = useState('')
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState<Action | null>(null)
  const [status, setStatus] = useState<{ action: Action | 'load'; message: string; error: boolean } | null>(null)

  useEffect(() => {
    let active = true
    loadDashboard().then(value => {
      if (active) {
        setData(value)
        setUsername(value.profile?.username ?? '')
        setMinutes(value.plan?.minutes ?? 45)
      }
    }).catch(() => {
      if (active) setStatus({ action: 'load', message: 'Could not load the dashboard. Check that FastAPI is running.', error: true })
    })
    return () => { active = false }
  }, [])

  async function submit(action: Action, payload: object, message: string) {
    setBusy(action)
    setStatus(null)
    let saved = false
    try {
      await api(action, payload)
      saved = true
      if (action === 'sessions') setFeedback('')
      setData(await loadDashboard())
      setStatus({ action, message, error: false })
    } catch (error) {
      setStatus({ action, message: saved ? 'Saved. Reload the page to refresh the dashboard.' : (error as Error).message, error: true })
    } finally {
      setBusy(null)
    }
  }

  function notice(action: Action | 'load') {
    return status?.action === action &&
      <p className={status.error ? 'notice error' : 'notice'} role={status.error ? 'alert' : 'status'}>{status.message}</p>
  }

  const plan = data?.plan
  const profile = data?.profile
  const used = plan?.items.reduce((total, item) => total + item.minutes, 0) ?? 0

  return <>
    <header className="topbar">
      <div className="shell topbar-inner">
        <a className="brand" href="#dashboard"><span aria-hidden="true" className="mark">LC</span> Daily Coach</a>
        <nav aria-label="Dashboard sections">
          <a href="#plan">Study plan</a><a href="#notes">Mistakes</a><a href="#progress">Progress</a><a href="#profile">Profile</a>
        </nav>
      </div>
    </header>
    <main className="shell py-9 sm:py-13" id="dashboard">
      <header className="mb-8">
        <p className="date-label">{displayDay(localDay())}</p>
        <h1>Your practice desk.</h1>
        <p className="muted mt-3">Plan today’s LeetCode practice and revisit what gave you trouble.</p>
      </header>
      {notice('load')}
      <div className="layout">
        <div className="space-y-5 min-w-0">
          <section id="plan">
            <h2>Today’s study plan</h2>
            <form className="row items-end" onSubmit={event => {
              event.preventDefault()
              void submit('plans', { minutes, day: localDay() }, 'Study plan saved.')
            }}>
              <div><label htmlFor="minutes">Available minutes</label>
                <input type="number" id="minutes" min={15} max={180} required value={Number.isNaN(minutes) ? '' : minutes}
                  onChange={event => setMinutes(event.target.valueAsNumber)} className="w-35" />
              </div>
              <button disabled={busy !== null}>{busy === 'plans' ? 'Planning…' : 'Generate plan'}</button>
            </form>
            {notice('plans')}
            {plan && <div className="mt-5">
              <p className="muted text-sm mb-2">{used} of {plan.minutes} minutes planned · {plan.source === 'ai' ? 'AI plan' : 'Rules-based plan'}</p>
              {!plan.items.length && <p>No new problems or due reviews fit this time budget.</p>}
              {plan.items.map(item => <article key={item.slug}>
                <div className="row justify-between">
                  <a className="font-semibold" href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
                  <span className="tag">{item.kind} · {item.minutes} min</span>
                </div>
                <p className="muted text-sm">{item.topic} · {item.difficulty}</p>
                <p className="mt-1">{item.reason}</p>
              </article>)}
            </div>}
            {!plan && <p className="muted mt-5">Your plan for today will appear here.</p>}
          </section>

          <section id="notes">
            <h2>Mistake knowledge base</h2>
            <form onSubmit={event => {
              event.preventDefault()
              void submit('sessions', { feedback, day: localDay() }, 'Practice session saved and reviews scheduled.')
            }}>
              <label htmlFor="feedback">How did practice go?</label>
              <textarea id="feedback" rows={3} className="w-full" required minLength={3} maxLength={4000}
                value={feedback} onChange={event => setFeedback(event.target.value)}
                placeholder="I solved Two Sum easily, but needed two hints for Group Anagrams." />
              <button className="mt-2" disabled={busy !== null || !data?.ai_enabled}>{busy === 'sessions' ? 'Analyzing…' : 'Analyze and save'}</button>
              {data && !data.ai_enabled && <p className="muted mt-2 text-sm">Set OPENAI_API_KEY on the backend to enable feedback analysis.</p>}
            </form>
            {notice('sessions')}
            {!!data?.weak_concepts.length && <div className="mt-5">
              <h3>Weak concepts</h3>
              <div className="row mt-2">{data.weak_concepts.map(concept =>
                <span className="tag" key={concept.name}>{concept.name} · {concept.count}</span>
              )}</div>
            </div>}
            <div className="mt-4">
              {data?.notes.map((note, index) => <article key={`${note.slug}-${index}`}>
                <div className="row justify-between">
                  <h3>{note.title}</h3><span className="muted text-sm">{displayDay(note.day)}</span>
                </div>
                <p className="muted text-sm">{note.topic} · {note.performance}{note.hints !== null && ` · ${note.hints} hints`}</p>
                {note.mistake && <p className="mt-1">{note.mistake}</p>}
                {note.takeaway && <p className="takeaway mt-1">{note.takeaway}</p>}
              </article>)}
              {data && !data.notes.length && <p className="muted">No mistake notes yet.</p>}
            </div>
          </section>
        </div>

        <aside className="space-y-5 min-w-0" aria-label="Profile and progress">
          <section id="profile">
            <h2>LeetCode profile</h2>
            <form onSubmit={event => {
              event.preventDefault()
              void submit('profile', { username: username.trim() }, 'Profile sync complete.')
            }}>
              <label htmlFor="username">Public username</label>
              <input className="w-full" id="username" autoComplete="off" required maxLength={40} value={username}
                onChange={event => setUsername(event.target.value)} pattern="[A-Za-z0-9_\x2D]+" placeholder="your-username" />
              <button className="mt-2" disabled={busy !== null}>{busy === 'profile' ? 'Syncing…' : profile ? 'Sync profile' : 'Connect profile'}</button>
            </form>
            {notice('profile')}
            {profile && <div className="mt-5">
              <a href={'https://leetcode.com/u/' + profile.username + '/'} target="_blank" rel="noreferrer">@{profile.username}</a>
              <dl className="counts mt-3">{['All', 'Easy', 'Medium', 'Hard'].map(label => <div key={label}>
                <dt>{label === 'All' ? 'Solved' : label}</dt><dd>{profile.counts[label] ?? '—'}</dd>
              </div>)}</dl>
              <p className="muted text-sm mt-3">Last sync {new Date(profile.synced_at).toLocaleString()}</p>
              {!profile.counts_available && <p className="notice">Fresh solved counts were unavailable.</p>}
              {!profile.recent_available && <p className="notice">Recent accepted submissions were unavailable.</p>}
            </div>}
          </section>
          <section id="progress">
            <h2>Study progress</h2>
            {data && <dl className="counts">
              <div><dt>Sessions logged</dt><dd>{data.progress.sessions}</dd></div>
              <div><dt>Plans generated</dt><dd>{data.progress.plans}</dd></div>
              <div><dt>Problems synced</dt><dd>{data.progress.synced_problems}</dd></div>
              <div><dt>Reviews due</dt><dd>{data.progress.due}</dd></div>
            </dl>}
            <h3 className="mt-5 mb-2">Review schedule</h3>
            {data?.reviews.map(review => <article key={review.slug} className="row justify-between">
              <a href={`https://leetcode.com/problems/${review.slug}/`} target="_blank" rel="noreferrer">{review.title}</a>
              <time dateTime={review.due} className={review.due <= localDay() ? 'takeaway' : 'muted'}>
                {review.due <= localDay() ? 'Due · ' : ''}{displayDay(review.due)}
              </time>
            </article>)}
            {data && !data.reviews.length && <p className="muted">Log a session to schedule reviews.</p>}
          </section>
        </aside>
      </div>
    </main>
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
