# Mission Control (Next.js + Vercel + Convex + Clerk)

Single-user “Mission Control” web app.

## Features (initial)
- **Task Board**: internal assistant tasks (separate from your Obsidian tasks)
- **Calendar**: scheduled tasks + OpenClaw cron jobs
- **Memory**: browse + search assistant memories (MEMORY.md + memory/*.md)
- **Model Usage**: overview of model usage + rate limit events

## Local dev
```bash
npm install
npm run dev
```

## Clerk setup
1. Create a Clerk app: https://dashboard.clerk.com
2. Configure **single-user** access:
   - Disable public signups
   - Allowlist: `andreas.allmaier@gmail.com`
3. Add env vars to `.env.local`:
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
CLERK_SECRET_KEY=...
```

## Convex setup
Convex requires an interactive login/config step.

Run locally in a real terminal:
```bash
npx convex dev --once --configure=new
```
Then add the generated env vars to `.env.local` (Convex will tell you what to add).

## Deployment (Vercel)
- Import this repo into Vercel
- Set the same env vars in Vercel project settings
- Deploy

## Notes
This repo includes the UI + stubs for Convex tables/queries/mutations. Once Convex is configured, switch the pages from mock data to live queries.
