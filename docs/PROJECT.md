# Nobu

**Nobu is a voice-driven job-outreach agent for freshers.** You tell it who to reach out to and for what role. It reads your resume, researches the company, decides what to highlight, finds the right person and a verified email, drafts a personalised cold email, and (after you approve) sends it and tracks follow-ups.

Status: planning. Phase 1 is a personal tool for one user (the author). Real users come later.

Name: Nobu, after the author's horse in Red Dead Redemption 2 and Ghost of Tsushima: loyal, and carries you where you need to go. "Nobu" is also the wake word for voice commands.

---

## 1. Problem

Freshers applying for jobs face the same grind on every application:

- Finding the right person to contact, and a working email for them.
- Researching each company well enough to write something that is not a template.
- Writing a personalised email, over and over.
- Remembering to follow up, and tracking who replied.

Generic tools (Apollo, Lemlist, AI SDR products) are built for sales teams. Nothing is built for a job seeker whose main asset is a resume and a handful of projects.

## 2. Vision

Say something like: *"Nobu, reach out to Acme for the backend intern role."* Nobu does the rest, shows you the draft with its reasoning, and waits for your approval. Everything doable by text is also doable by voice.

## 3. Goals and non-goals

**Goals (Phase 1, personal use)**
- Cut the time per outreach from ~30 minutes to ~2 minutes of review.
- Drafts that are specific enough to get replies: one real project tied to one real thing the company does.
- Reliable follow-up tracking so no opportunity is forgotten.
- Voice parity: every text action has a voice equivalent.

**Non-goals (for now)**
- Multi-user accounts, billing, public launch.
- Bulk or automatic mass emailing. This is deliberately low-volume.
- Scraping LinkedIn or X through a logged-in account (see Guardrails).
- Auto-sending without approval.

## 4. Core principles

1. **Human approves every send.** The agent proposes, you decide. Follow-ups also need approval at first.
2. **Grounded claims only.** Every statement about you must trace to your resume fact bank. Every statement about the company must trace to a researched source.
3. **Show the reasoning.** Each draft displays why it picked a given project and a given contact.
4. **Quality over volume.** Hard daily cap, deduplication, suppression list.
5. **Safe data sources.** Licensed APIs and public web pages, not logged-in scraping.
6. **Confidence-gated.** Low-confidence email addresses are never sent to without explicit override.

## 5. User flow

1. One-time: upload resume, set preferences (target roles, tone, daily cap, sign-off, links to GitHub/portfolio).
2. Give a command by voice or text: company, role, optionally a job URL or a contact.
3. Agent runs the pipeline (section 7) and returns a **review card**: chosen contact (with confidence and why), draft email, the fact(s) it highlighted and why, any critic flags.
4. You edit by hand or by voice ("make it shorter", "mention my hackathon win"), then approve.
5. Agent reads back recipient and subject and waits for an explicit yes, then sends via Gmail.
6. The outreach enters tracking. Follow-ups are proposed on schedule and need approval.

## 6. Features

### 6.1 Resume ingestion and fact bank
- Upload PDF/DOCX/TXT, extract text, and have an LLM produce structured JSON.
- Store as a **fact bank**: each fact has a type (project, experience, skill, achievement, education), a short description, tech used, outcomes or numbers if stated, links, and tags.
- User can review and edit the fact bank. The agent only ever cites facts that exist here.

### 6.2 Command intake
- Free-form text or voice transcript parsed into a structured request: company, role, job URL (optional), contact (optional), notes.
- If something essential is missing or ambiguous (e.g. mis-heard company name), the agent confirms before spending any research or lookup credits.

### 6.3 Company research
- Fetch the company site (home, about, careers/blog), the job post if given, and recent public news via web search.
- Produce a compact **company brief**: what they build, stack signals, stage/size, recent news, what the role likely needs, with source URLs.

### 6.4 Matching ("think itself")
- Score fact-bank items against the company brief and role.
- Select the best one or two facts, and write a one-line rationale per choice.
- The rationale is shown to the user and can be overridden.

### 6.5 Contact discovery
- Decide **who** to target by company size and role: founder or engineering lead for small startups; recruiter or hiring manager for larger companies. State why.
- Find candidates through the company site, the job post, and a contact-data provider behind an adapter interface (Hunter, Apollo, Snov, etc.).
- Infer address patterns (first.last@domain) only when the provider confirms the pattern for that domain; verify through the provider.
- Confidence score per address. Suggested thresholds: 0.8 or higher proposes normally; 0.5 to 0.8 asks the user; below 0.5 skips.

### 6.6 Drafting and critic
- Draft rules: under about 120 words; specific subject line; one concrete link between a fact and the company; one clear ask; resume/GitHub link; no flattery filler; no invented claims.
- **Critic pass:** a second LLM call checks every factual claim against the fact bank and company brief and returns flags. The review card shows flags, and a draft with unresolved flags cannot be sent.

### 6.7 Review and approval UI
- Editable subject and body, the highlighted facts with rationale, contact and confidence, sources used.
- Text-to-speech read-back of the draft.
- Approve, edit, regenerate, or discard.

### 6.8 Sending
- Gmail API with the `gmail.send` scope. Personal mode runs the OAuth app in Google's "Testing" mode with the author's own account.
- **Dry-run mode** on by default: builds and logs the message without sending.
- Hard daily cap (default 15, configurable), per-contact and per-company dedupe window (default 60 days), suppression list.

### 6.9 Tracking and follow-ups
- Every outreach moves through the state machine in section 9.
- Reply detection by checking the sent thread for replies (personal mode needs a read scope such as `gmail.readonly`, which is fine in testing mode but becomes a restricted scope in a public product; see Productization).
- Bounce detection from delivery-failure messages.
- Follow-up policy: first follow-up about 6 to 7 days after sending, second about 7 days later, maximum two, never after a reply or bounce. Each follow-up must add something new (a new project update, a relevant company news item), not "just bumping this".
- A dashboard showing pending, due follow-ups, replied, bounced, closed.

### 6.10 Hiring-signal discovery (later phase)
- Find companies currently hiring for the user's target roles from public sources: careers pages, public job boards, "Who is hiring" threads, public posts found through web search.
- Suggest targets to the user as a queue. Nothing is emailed without the normal approval flow.
- No logged-in LinkedIn or X scraping.

### 6.11 Voice layer
Voice is a thin layer over the same actions the UI uses. Speech recognition starts with the browser's built-in API behind an interface so it can be swapped for Whisper or Deepgram later. Read-back uses text-to-speech.

| Intent | Example utterance |
|---|---|
| New outreach | "Nobu, reach out to Acme for the backend intern role" |
| Edit draft | "Make it shorter", "Mention my hackathon win", "Change the subject" |
| Override match | "Use my Scouter project instead" |
| Read back | "Read it to me" |
| Approve and send | "Send it" (agent reads back recipient and subject, requires explicit "yes") |
| Discard | "Discard this one" |
| Status | "What's pending?", "Who haven't replied?" |
| Follow-up | "Show follow-ups due today", "Draft the follow-up for Acme" |
| Mark | "Acme replied", "Close Acme" |

Rules: "Nobu" is the wake word (or a push-to-talk button, which should be the default since always-on listening is unreliable in a browser); confirm what was heard for company names; never send on a single ambiguous utterance; sending always needs an explicit confirmation turn.

## 7. Agent pipeline

Implemented as a graph (LangGraph) with a human-in-the-loop interrupt before sending.

1. **parse_command**: transcript or text to a structured request.
2. **research_company**: fetch and summarise sources into a company brief.
3. **match_facts**: pick facts and rationale.
4. **find_contact**: choose target person, discover and verify email, score confidence.
5. **draft_email**: generate subject and body.
6. **critic**: validate claims and style rules, return flags.
7. **review (interrupt)**: wait for the user.
8. **send**: dry-run or real send, record events.
9. **track**: schedule follow-up checks and reply detection.

Each node writes its inputs, outputs and sources to the database so every draft can be audited.

## 8. Architecture and stack

Chosen to match the author's existing skills.

- **Backend:** Python, FastAPI, LangGraph, SQLAlchemy.
- **Database:** PostgreSQL (SQLite is fine for the very first skeleton).
- **Frontend:** React (Vite) with a single review-centric UI and a mic button.
- **Background jobs:** a simple scheduler or queue for follow-up checks and reply polling.
- **LLM:** Anthropic API, model name read from an environment variable so it can be changed.
- **Voice:** browser speech recognition and speech synthesis first, with a provider interface.
- **Integrations:** Gmail API, one contact-data provider through an adapter, web search and page fetching for research.
- **Packaging:** Docker Compose for local development.
- **Secrets:** environment variables; OAuth tokens encrypted at rest.

### 8.1 Project location and layout

- Claude Code runs from the author's **Desktop directory**. The whole project lives in a new folder named **Nobu** inside it (for example `~/Desktop/Nobu` on macOS/Linux, or `C:\Users\<name>\Desktop\Nobu` on Windows).
- Everything for the project (code, docs, config, Docker files, tests) stays inside the `Nobu` folder. Nothing is created elsewhere on the Desktop.
- This specification is kept at `Nobu/docs/PROJECT.md`.
- `Nobu` is its own git repository (`git init` inside the folder). Suggested top-level layout: `backend/`, `frontend/`, `docs/`, `docker-compose.yml`, `.env.example`, `README.md`.

## 9. Outreach state machine

`drafted` to `approved` to `sent`, then one of `replied`, `bounced`, `followup_1_due` to `followup_1_sent` to `followup_2_due` to `followup_2_sent` to `closed`.

- `replied` and `bounced` stop all follow-ups.
- `discarded` is reachable from `drafted` or `approved`.
- Every transition writes an event row with timestamp and actor (user, agent, system).

## 10. Data model (initial)

- **profile:** user settings, tone, sign-off, links, daily cap, dry-run flag.
- **resume:** raw file reference and extracted text.
- **fact:** resume_id, type, description, tech, outcome, links, tags.
- **company:** name, domain, brief (JSON), sources (JSON), fetched_at.
- **contact:** company_id, name, title, email, source, confidence, verified_at.
- **outreach:** company_id, contact_id, role, state, subject, body, highlighted_fact_ids, rationale, critic_flags, thread_id, sent_at.
- **event:** outreach_id, type, detail, actor, created_at.
- **suppression:** email or domain, reason.

## 11. Guardrails

- Dry-run on by default; real sending is an explicit setting.
- Daily cap, dedupe window and suppression list enforced in code, not only in prompts.
- Critic must pass before sending.
- No auto-send of first emails or follow-ups in Phase 1.
- Never guess an email without a confidence score and the user's awareness.
- Respect opt-outs: if someone asks not to be contacted, add them to suppression immediately.
- Do not use logged-in LinkedIn or X sessions for scraping or automation.
- Comply with applicable rules on commercial email and data protection (India's DPDP Act, and GDPR/CAN-SPAM if relevant). Include a sensible way for recipients to opt out.

## 12. Security and privacy

- Local-first in Phase 1: resume and data stay on the author's machine.
- Encrypt OAuth tokens and API keys; never commit them.
- Minimal Gmail scopes.
- A "delete all my data" command from day one.

## 13. Roadmap

- **Phase 0, skeleton:** repo, Docker Compose, FastAPI, DB schema, config, LLM wrapper, test harness with a stub LLM.
- **Phase 1, text flow:** resume to fact bank; command to research to match to draft to critic to review UI; dry-run send.
- **Phase 2, real sending and tracking:** Gmail OAuth and send, state machine, reply and bounce detection, follow-up proposals, dashboard.
- **Phase 3, voice:** speech input and read-back, intent router, confirmation rules.
- **Phase 4, discovery:** contact provider integration with confidence scoring, hiring-signal queue from public sources.
- **Phase 5, productization:** multi-user auth, per-user OAuth, Google OAuth verification (the broader read scope used for reply detection is a restricted scope that requires a paid third-party security assessment, so consider alternatives such as sending through a service or manual "mark replied"), billing and per-user cost controls, privacy compliance, onboarding for freshers.

## 14. Success metrics

- Minutes of user effort per outreach (target under 3).
- Reply rate (positive or neutral) over a rolling window.
- Bounce rate (keep very low).
- Critic flag rate and how often the user rewrites the draft heavily.
- Follow-ups sent on time.

## 15. Things to verify before relying on them

- Current Gmail API scope classifications and send limits (Google changes these).
- Current free-tier limits and pricing of the contact-data provider chosen.
- Browser speech-recognition support and accuracy for Indian-English accents; plan a Whisper or Deepgram fallback.

## 16. Open questions

- Which contact-data provider first (cost, coverage, India and startup coverage)?
- Preferred tone and length for the author's emails (sample emails would help tune the drafter).
- Should resume tailoring (a role-specific resume version) be in scope later?
- Trademark: "Nobu" is also a well-known restaurant and hotel brand. Fine for personal use; check before any public launch and consider a qualifier or a different public name.
