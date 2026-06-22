# CLAUDE.md — <PROJECT NAME>

> Fill in the four lines under **Project** per repo.
> Everything under **Guedes Ventures Standards** is fixed across every project — do not change it without being told to.

## Project
- **What it is:** <one line — e.g. "AI receptionist landing page for skilled-trade contractors">
- **ICP (one sentence):** <who they are, size, pain, why they pay>
- **Live URL:** <e.g. https://joinfluxo.com>
- **Stack:** <e.g. single-file HTML | React + Node | Flask + Postgres>

---

## Guedes Ventures Standards (do not change)

### Brand system
- Background: `#0A0A0A`
- Accent (green): `#A3E635`
- Font: monospace
- Separator motif: `///`
- Footer + favicon are injected by a single `brand.js`. Import it — never hand-copy footer/favicon markup into individual pages. If `brand.js` isn't in the repo yet, ask before creating one.

### Build conventions
- Landing pages: prefer a single self-contained HTML file unless the project clearly needs more.
- Apps: follow the stack named in **Project** above. Don't introduce a different framework on your own.
- Keep edits minimal and scoped to the task. Do not refactor, rename, or reformat unrelated files without asking first.
- No new dependency, third-party service, or external API without asking first and explaining why.

### Deploy pipeline
- Host: **Vercel**, auto-deploys on push to `main`.
- Flow every time: you write the files → you show me the diff → I approve → only then commit and push.
- **Never push to `main` (production) without my explicit OK in this session.** When in doubt, stage the change and stop.
- Ask before any destructive git operation (force-push, history rewrite, branch or file deletion, `reset --hard`).
- After a deploy, give me the live URL and a one-line summary of what changed.

### Working rules
- If you're unsure about a fact, a requirement, or how something behaves: say "I don't know" and ask. Do not guess or fill gaps with plausible-sounding assumptions.
- State any assumption you do make inline, so I can catch it.
- Prefer the simplest thing that works. Flag it if I'm asking for something more complex than the problem needs.
- Keep secrets (API keys, tokens, Stripe keys, phone numbers) out of committed files. Use environment variables; never hardcode or print them.

---

## Notes for this repo
<scratchpad for project-specific gotchas as they come up — e.g. "Twilio number is agents-only", "Make.com webhook lives at /hook/xyz">
