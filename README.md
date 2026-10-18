# LedgerLens — Week 2 "Side Hustle" build (DEV Hacktoberfest Open-Source AI Challenge)

## Lane
- Challenge: Hacktoberfest Open-Source AI Challenge Week 2 — "Side Hustle"
- URL: https://dev.to/challenges/hacktoberfest-week2-2026-10-12
- Window: Oct 12 → Oct 18, 2026 (7 days; hub shows "Ends in 7 days")
- Prizes: **$2,550 across 18 winners** — 1 overall ($250 + DEV++ membership + badge),
  6 featured partner categories ($200 each), 11 partner categories ($100 each)
- Theme: "Build something with open-weight models or open-source AI that
  someone would actually pay for." Judging: **Writing Quality weighted MOST**,
  then Relevance to Prompt/Theme, Creativity, Technical Execution,
  Use of Partner Technology (optional)
- Bonus points for landing a first user. New project built inside the
  challenge window (required — repos must start and complete in-window).

## The project: LedgerLens
A local-first bookkeeping agent for freelancers/gig workers: drop in invoices
and receipts (CSV or plain text), get back categorized books, tax-ready
category totals, overdue-invoice nudges, and a 3-month cash-flow forecast —
all on your own machine, $0/month, client data never touches a server.

Pitch angle (Side Hustle): QuickBooks is ~$30/mo and your client data lives on
their server. LedgerLens is free, private, and keeps the money in the
freelancer's pocket — the open pieces (local models/agent harness possible,
stdlib-only engine now) are exactly what make the unit economics work.

## Partner-category targets
- **Overall $250** — primary target; writing quality is the weighted criterion.
- **Best Use of Entire ($100)** — writeup shares the agent sessions behind the
  build (devrelay embed optional).
- **Best Use of Sentry Agent Tracing ($100)** — writeup includes traces/
  screenshots: setup, latency, tokens, cost, what was found while debugging.
- **Best Use of TabPFN ($200)** — stretch: would need platform.priorlabs.ai
  signup + free non-commercial license key (a his-tap); the cashflow module
  has a ForecastBackend interface ready for it. Not required for overall.

## Status
- [x] Core built: parse / categorize / cashflow / report (stdlib-only)
- [x] test_flow.py passing
- [x] demo.py CLI end-to-end on synthetic fixture data
- [x] WEEK2-DRAFT.md — DEV post draft (his-tap: review + publish on DEV)
- [x] webdemo.py — screen-recordable demo UI (built 2026-10-12 ~17:35 EDT:
  stdlib http.server on 127.0.0.1:8137, paste-CSV/text form + synthetic-fixture
  button, report page w/ totals/overdue/forecast/actions + record table +
  confidence bars, /api/report JSON, per-session history, HTML-escaped,
  200 KB input cap; 35/35 tests, live smoke verified incl. XSS negative)
- [x] video-assets/terminal-demo-render.mp4 — paced demo video backbone
  (2026-10-12 ~18:30 EDT: REAL `script` capture of `python3 demo.py` exit 0,
  rendered offline PIL+ffmpeg 28s 1280x720@30 H.264, all frames inspected:
  title card + categorization reveal + full bookkeeping report clean,
  no truncated text, no overlapping labels; renderer streams frames to
  ffmpeg — no frame-list accumulation; word-boundary wrap)
- [ ] Fresh GitHub repo + published DEV post (his taps; repo must be created
      in-window per challenge rules)
- [ ] DevRelay agent-session embed (optional; his-tap if he wants the account)
