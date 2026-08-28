# Aramco Asset Digitization Dashboard

Multipage Streamlit app for tracking digitization progress across media
categories (Magnetic Tapes, Film Reels, Still Images, and any future categories).

- **Login required.** A signed browser cookie (30 days by default) keeps the
  same machine logged in without re-prompting.
- **Dashboard** – combined summary across all categories, plus week-on-week and
  month-on-month digitization growth and trend charts.
- **Data View** – pick a category and filter on any column; browse and export.
- **Data Import** (admin only) – refresh the database from the Excel workbook.

Data lives in a database (SQLAlchemy): a local **SQLite** file for development,
hosted **Postgres (Neon)** in production. Excel stays the data-entry tool.

## Project layout

```
app.py              entry point: auth gate + page routing
lib/
  config.py         DB URL / auth config (env vars > Streamlit secrets > defaults)
  db.py             SQLAlchemy engine, `assets` table, cached read queries
  ingest.py         workbook -> cleaned dataframe -> replace `assets`
  auth.py           streamlit-authenticator wiring
  metrics.py        week/month growth math
views/
  dashboard.py      Home
  data_view.py      Per-category filtered table
  admin_upload.py   Admin upload page
import_data.py      CLI importer (first load / very large files)
```

## Local setup

```powershell
pip install -r requirements.txt
```

1. `.streamlit/secrets.toml` is already present with SQLite and the real login
   accounts (admin `akash`, plus six viewers). Usernames are case-insensitive.

   To add or change an account, generate a password hash:
   ```powershell
   python -c "import streamlit_authenticator as a; print(a.Hasher.hash('YOUR_PASSWORD'))"
   ```
   Paste the `$2b$...` value as `password` under
   `[auth.credentials.usernames.<name>]`. Add more `[auth.credentials.usernames.X]`
   blocks for more users; list admins in `admin_users`.

2. Load data into the local SQLite database:
   ```powershell
   python import_data.py "URL Dashboard Database Testing.xlsx"
   ```

3. Run:
   ```powershell
   streamlit run app.py
   ```
   Log in. Reload the tab — you stay logged in (cookie). Use a private window to
   see the login prompt again. "Log out" (sidebar) clears the cookie.

## Deploy to Streamlit Community Cloud (one time)

Streamlit Community Cloud hosts the app for free from a GitHub repo and gives you
a `https://<name>.streamlit.app` URL to share with the team.

### 1. Install git and create a GitHub account

- Install git: `winget install Git.Git` (then open a new terminal), or
  <https://git-scm.com/download/win>.
- Create a free account at <https://github.com> and a **new repository** (Private
  is fine), e.g. `aramco-dashboard`. Don't add a README/gitignore — this project
  already has them.

### 2. Push this project to GitHub

```powershell
cd "d:\Work\Aramco\AramcoDashboard"
git init
git add .
git status          # CONFIRM .streamlit/secrets.toml and aramco.db are NOT listed
git commit -m "Aramco digitization dashboard"
git branch -M main
git remote add origin https://github.com/<your-user>/aramco-dashboard.git
git push -u origin main
```

`.gitignore` already keeps `secrets.toml`, `aramco.db`, and `*.xlsx` out of the
repo — secrets live only in the Streamlit Cloud settings (step 4).

### 3. Create the production database (Neon Postgres, free)

1. Sign up at <https://neon.tech>, create a project (pick a region near the team).
2. Copy the connection string. It looks like:
   `postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require`
3. Change the prefix to `postgresql+psycopg2://` — this is your `DATABASE_URL`.
4. Load the data into it from your machine:
   ```powershell
   $env:DATABASE_URL = "postgresql+psycopg2://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require"
   python import_data.py "URL Dashboard Database Testing.xlsx"
   ```

### 4. Create the app

1. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app** →
   **Deploy a public app from GitHub**.
2. Repository: your repo. Branch: `main`. Main file path: `app.py`.
3. Open **Advanced settings → Secrets** and paste your local
   `.streamlit/secrets.toml`, but replace the `[db].url` line with the Neon
   `postgresql+psycopg2://...` string. Keep the whole `[auth]` block as-is.
4. Click **Deploy**. After a minute you get the app URL — share it with the team.
   They just open it and log in with the usernames/passwords in the `[auth]` block.

## Making changes after deployment

| What changed | How to ship it |
| --- | --- |
| **Code** (pages, charts, logic) | Edit locally, test with `streamlit run app.py`, then `git add .` → `git commit -m "..."` → `git push`. Streamlit Cloud redeploys automatically in ~1 minute. |
| **Logins / secrets / DB URL** | Edit in the Streamlit Cloud dashboard: your app → **Settings → Secrets** → save. The app reboots itself. No git push needed. |
| **The asset data** | Log in as an admin, use the **Data Import** page to upload a new workbook. For very large files, run `import_data.py` locally with `DATABASE_URL` set to Neon. No git push needed. |

Keep your local copy in sync by editing there, and never commit `secrets.toml`.

## Notes

- Community Cloud apps sleep after a period of no traffic and wake on the next
  visit (~30 s cold start). This is normal on the free tier.
- Neon free tier gives ~0.5 GB storage and auto-suspends the database when idle;
  watch storage usage as the data grows toward 2M rows.
- All filtering/counting runs in SQL — the app never loads the full table into
  memory, so it scales to ~2M rows.
- Adding a new category later is just a new sheet in the workbook; the app picks
  it up on the next import. New/unknown columns are preserved as JSON in an
  `extra` column rather than breaking the import.
