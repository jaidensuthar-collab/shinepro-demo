# Workspace guide for Claude

This repo holds two things:

1. `index.html` — the live ShinePro car-detailing chatbot demo. Leave it alone unless a job is explicitly about it.
2. `neighbor/` — tech work for a client in Jaiden's neighborhood. **Most requests in this repo are jobs for her.**

## When Jaiden sends a job

Requests usually arrive from a phone and may be short or informal ("fix her printer instructions", "make a flyer for the bake sale"). Handle them like this:

1. Read `neighbor/client.md` first for who she is, her devices, accounts, and preferences.
2. Create `neighbor/jobs/YYYY-MM-DD-short-slug.md` from `neighbor/jobs/_template.md`, filling in the request in Jaiden's words.
3. Do the work. Put files she'll receive (documents, images, spreadsheets, web pages, scripts) in `neighbor/deliverables/<same-slug>/`.
4. Fill in the job file's Result, Time spent, and Follow-ups sections.
5. Add a one-line row to `neighbor/jobs/LOG.md`.
6. If you learn something lasting about her setup (new device, account, preference), update `neighbor/client.md`.
7. Commit and push.

Ask Jaiden a question only when a job truly can't proceed without it; otherwise make a sensible call and note the assumption in the job file.

## Style for anything she will read

- She is not a tech person. Plain language, short steps, no jargon. Number every step.
- Say exactly what she'll see on screen ("tap the blue **Settings** button").
- Prefer printable one-pagers for how-to guides.

## Privacy

- Never commit passwords, PINs, recovery codes, card numbers, or full account numbers. If one is needed, write `<ask Jaiden>` instead.
- Keep her personal details to what a job needs.
