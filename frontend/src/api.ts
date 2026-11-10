export type Fact = {
  id: number
  type: 'project' | 'experience' | 'skill' | 'achievement' | 'education'
  description: string
  tech: string[]
  outcome: string
  links: string[]
  tags: string[]
}

export type Profile = {
  name: string
  tone: string
  sign_off: string
  links: Record<string, string>
  target_roles: string[]
  daily_cap: number
  dry_run: boolean
  has_resume: boolean
}

export type Parsed = {
  company: string
  role: string
  company_domain: string
  job_url: string
  contact_name: string
  contact_email: string
  notes: string
}

export type Flag = { index: number; code: string; message: string; source: string; resolved: boolean }

export type Card = {
  id: number
  state: string
  role: string
  company: { name: string; domain: string } | null
  contact: { email: string; name: string; title: string; confidence: number; source: string } | null
  subject: string
  created_at: string
  sent_at: string | null
  unresolved_flags: number
  body?: string
  flags?: Flag[]
  highlighted?: { fact_id: number; description: string; rationale: string; company_point: string }[]
  contact_rationale?: string
  sources?: string[]
  send_problems?: string[]
  dry_run?: boolean
}

export class ApiError extends Error {
  problems: string[]
  constructor(message: string, problems: string[] = []) {
    super(message)
    this.problems = problems
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body instanceof FormData) {
    init.body = body
  } else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  const res = await fetch(`/api${path}`, init)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    throw new ApiError(detail || res.statusText, data.problems ?? [])
  }
  return data as T
}

export const api = {
  profile: () => call<Profile>('GET', '/profile'),
  saveProfile: (p: Omit<Profile, 'dry_run' | 'has_resume'>) => call<Profile>('PUT', '/profile', p),
  uploadResume: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return call<{ facts: number }>('POST', '/resume', fd)
  },
  facts: () => call<Fact[]>('GET', '/facts'),
  addFact: (f: Omit<Fact, 'id'>) => call<Fact>('POST', '/facts', f),
  updateFact: (f: Fact) => call<Fact>('PUT', `/facts/${f.id}`, f),
  deleteFact: (id: number) => call<unknown>('DELETE', `/facts/${id}`),
  parse: (text: string) => call<{ parsed: Parsed; issues: string[] }>('POST', '/outreach/parse', { text }),
  run: (request: Parsed) => call<Card>('POST', '/outreach', { request }),
  list: () => call<Card[]>('GET', '/outreach'),
  get: (id: number) => call<Card>('GET', `/outreach/${id}`),
  edit: (id: number, subject: string, body: string) =>
    call<Card>('PATCH', `/outreach/${id}`, { subject, body }),
  regenerate: (id: number, instructions: string) =>
    call<Card>('POST', `/outreach/${id}/regenerate`, { instructions }),
  resolveFlag: (id: number, index: number) => call<Card>('POST', `/outreach/${id}/flags/${index}/resolve`),
  setContact: (id: number, email: string, name: string) =>
    call<Card>('PUT', `/outreach/${id}/contact`, { email, name }),
  approve: (id: number) => call<Card>('POST', `/outreach/${id}/approve`),
  discard: (id: number) => call<Card>('POST', `/outreach/${id}/discard`),
  send: (id: number) => call<Card>('POST', `/outreach/${id}/send`, { confirm: true }),
  suppress: (value: string, reason: string) => call<unknown>('POST', '/suppression', { value, reason }),
  deleteAll: () => call<unknown>('POST', '/data/delete-all', { confirm: 'DELETE' }),
}
