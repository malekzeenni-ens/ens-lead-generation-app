# Local setup

## Prerequisites

- Windows 10/11 with WebView2 and Microsoft C++/Windows build tools required by Tauri
- Python 3.13
- `uv`
- Node.js 22 or newer and npm (the kickoff machine uses Node 24)
- Stable Rust with Cargo, rustfmt, and Clippy

No provider credentials are needed to run scoring, matching, shortlists, or any existing-lead workflow. Google Places and Meta Instagram credentials are optional and are needed only for their external discovery sources.

## Install the locked workspace

From the repository root:

```powershell
uv sync --all-packages --dev --locked
npm.cmd ci
```

PowerShell on the kickoff machine blocks `npm.ps1`; use `npm.cmd` as shown. Copy `.env.example` only for a deliberate local override and never place credentials in it. The application does not auto-load repository `.env` files.

## Run in desktop development mode

After the one-time install above, Windows users can double-click `Start Etch N Shine.cmd` in the repository root. Keep its command window open while the desktop app is running; it owns the development process and displays any startup failure.

```powershell
npm.cmd run desktop:dev
```

Tauri starts Vite on `127.0.0.1:1420`, finds the repository `.venv`, selects an ephemeral backend port, generates the session token, runs Alembic migrations, and shuts the backend down with the desktop host.

The desktop runner places Cargo output under `%LOCALAPPDATA%\EtchNShine\Build\cargo-target`. This avoids Dropbox file locks in the repository and applies whether the app is started from the command file or with `npm.cmd run desktop:dev`.

This is a development runner, not an installer. No installer build is required to work on or use the application locally.

Default data is written to `%LOCALAPPDATA%\EtchNShine\LeadGeneration`, not the repository. For isolated backend testing, set `ENS_DATABASE_PATH` and `ENS_LOG_DIRECTORY` to disposable absolute paths.

## Optional Google Places discovery

Create a restricted Google Maps Platform API key with the Places API (New) and Geocoding API enabled, configure billing/budget alerts in Google Cloud, and expose the key only to the backend process:

```powershell
$env:ENS_GOOGLE_PLACES_API_KEY = 'your-restricted-key'
$env:ENS_DISCOVERY_MAX_RESULTS = '40'
$env:ENS_DISCOVERY_MAX_QUERIES = '3'
npm.cmd run desktop:dev
```

Environment variables must be set in the terminal that launches the app. The repository does not auto-load `.env` files and the key is never stored in SQLite or sent to the frontend. In **Campaigns**, select **Discover with Google Places** on the campaigns that may use the provider. A run without that selection refreshes existing leads only. AI and outbound messaging remain disabled in either mode.

## Optional Instagram profile import and enrichment

Instagram uses the official Meta API with Facebook Login. Your Instagram professional account must be linked to a Facebook Page, and your Meta developer app must have the required testing permissions/features.

1. In Meta's Facebook Login settings, add this exact **Valid OAuth Redirect URI**: `http://localhost:8766/meta/oauth/callback`. Meta treats `localhost` as its local-development exception; the numeric `127.0.0.1` form is rejected by the current dashboard's HTTPS validation.
2. In the Meta app, make `pages_show_list`, `pages_read_engagement`, and `instagram_basic` available for testing. The app does not request publishing, messaging, comment, insights, advertising or business-administration scopes.
3. Start the desktop app and open **Settings → Instagram via Meta**.
4. Enter the Meta App ID and App Secret there. Do not place either value in source, `.env`, a screenshot or chat. The App Secret and resulting access tokens are encrypted with Windows DPAPI for the current Windows user and are not stored in SQLite or frontend storage.
5. Click **Connect Instagram with Meta**, complete Facebook authorization in the browser, and return to the app. If Meta returns more than one connected Instagram professional account, select the Page/account pair to use.
6. Open **Campaigns â†’ Social leads â†’ Instagram import**, select the campaign, paste one public Instagram professional-profile URL, and choose **Fetch from Meta**.
7. Review the returned profile and choose **Import, score and match**. The backend re-fetches the profile, deduplicates it by stable Meta ID/social handle/contact identity, enriches its public website when available, and runs campaign scoring, product matching and shortlist evaluation.
8. Use **Enrich saved Instagram profiles** in Social leads, or enable Instagram enrichment on the campaign and use **Refresh Instagram profiles**, to recheck all Instagram handles already attached to that campaign. Google Places and scoring-only remain separate actions.

The Meta app can remain unpublished while testing with an app admin, developer or tester account and the Instagram/Page assets that account manages. App review and any applicable business verification are required before accounts outside the app's roles can connect. Meta returns only accessible professional accounts; it does not provide arbitrary consumer-profile search or exact-radius location search. Consumer, private, misspelled or otherwise unavailable profiles are shown as explicit failures and are not silently skipped. The campaign location is stored only as review context. Repeated imports link to the existing lead instead of creating duplicates. Instagram cold-DM sending remains disabled.

Facebook lead capture remains an assisted workflow under Social Leads; there is not yet an automatic Facebook discovery provider. It is therefore not bundled into the Instagram or Google buttons.

The **Find profiles** Instagram buttons open the campaign's location-and-keyword hashtag directly in Instagram. Facebook buttons use targeted public Google searches because Facebook has no equivalent dependable public discovery route. These actions do not import or scrape results. Meta hashtag media does not expose a dependable post-author identity to the app, so select a relevant profile yourself and paste its URL into **Instagram import**. Facebook remains a separate verified manual capture form. **All leads** shows the recorded origin for each lead and can filter Google Places, Instagram, Facebook and Manual sources.

## Run the quality gates

```powershell
npm.cmd run quality
```

This checks both lockfiles, npm high-severity audit, frontend lint/type/tests/build, Python lint/format/types/tests/coverage, and Rust format/tests/Clippy. Generated frontend coverage and Cargo output are placed under `%LOCALAPPDATA%\EtchNShine\Build` to avoid Dropbox sync locks.

## Run the backend and frontend as separate servers

Choose one non-secret development token of at least 24 characters. In the first terminal, from `apps/backend`:

```powershell
$env:ENS_SESSION_TOKEN = 'local-development-token-change-me'
$env:ENS_PORT = '8765'
uv run python -m app.cli serve
```

In a second terminal, set the matching frontend values and start Vite from the repository root:

```powershell
$env:VITE_ENS_API_URL = 'http://127.0.0.1:8765/api/v1'
$env:VITE_ENS_SESSION_TOKEN = 'local-development-token-change-me'
npm.cmd run frontend:dev
```

Open `http://127.0.0.1:1420`. The server refuses a non-loopback `ENS_HOST`, and every API request requires the matching token in `X-Session-Token`. The desktop development host remains the simplest option because it generates and transports the token automatically.

## Seed/demo data

No automatic seed command is required. Create campaigns and manual leads through the application so the same validation, evidence, stage, and audit paths are exercised. Lead CSV loading remains intentionally outside the current increment.

Catalogue products can be added manually or loaded from a Shopify product export through **Catalogue → Upload Shopify listing CSV**. A disposable example is available at `docs/testing/shopify-products-sample.csv`. The browser reads the selected file locally; the API stores only normalised editable products, not the raw CSV.
