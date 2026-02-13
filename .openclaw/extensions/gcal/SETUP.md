# Google Calendar (gcal) OpenClaw plugin — setup

This plugin uses **OAuth2 + a refresh token** to access Google Calendar.

## 1) Create an OAuth client in Google Cloud

1. Go to Google Cloud Console: https://console.cloud.google.com/
2. Create/select a project.
3. Enable the API: **APIs & Services → Library → Google Calendar API → Enable**.
4. Configure consent screen (if you haven’t): **APIs & Services → OAuth consent screen**.
   - For personal use you can usually use “External” + add yourself as a test user.
5. Create credentials: **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application** (recommended)
   - Authorized redirect URI: pick one you can run locally, e.g.
     - `http://localhost:3000/oauth2callback`

You will get:
- **Client ID**
- **Client secret**

## 2) Obtain a refresh token

Google only returns a refresh token when you request **offline** access and force a consent screen at least once.

### Option A (recommended): Use Google OAuth Playground

1. Open: https://developers.google.com/oauthplayground/
2. Click the gear icon (top right) and check:
   - “Use your own OAuth credentials”
3. Paste your **Client ID** + **Client secret**.
4. In Step 1, select scopes (minimum):
   - `https://www.googleapis.com/auth/calendar`
   - (or use read-only: `https://www.googleapis.com/auth/calendar.readonly`)
5. Click **Authorize APIs**.
6. In Step 2, click **Exchange authorization code for tokens**.
7. Copy the **Refresh token**.

### Option B: Generate via a small local script

If you prefer code, you can write a tiny Node script that:
- builds an auth URL with `access_type=offline` and `prompt=consent`
- opens it, then exchanges the returned code for tokens

(If you want, ask the main agent to generate this helper script for your exact redirect URI.)

## 3) Configure OpenClaw

Add plugin config under `plugins.entries.gcal.config` (do **not** paste secrets into chat logs).

Config fields (from `openclaw.plugin.json`):
- `clientId` (required)
- `clientSecret` (required)
- `redirectUri` (required)
- `refreshToken` (required)
- `calendarId` (optional; default: `primary`)
- `scopes` (optional; default: `["https://www.googleapis.com/auth/calendar"]`)

## 4) Enable the tool for your agent

The tool is registered as **optional**, so it must be allowlisted:
- add `gcal` (plugin id) or `gcal` (tool name) to your agent’s tools.allow

Then restart the Gateway.

## Notes / pitfalls

- If you used the read-only scope, create/update/delete will fail with 403.
- If you don’t get a refresh token, re-run the auth flow with `prompt=consent` and `access_type=offline`.
- Some Google Workspace orgs restrict 3rd-party OAuth apps.
