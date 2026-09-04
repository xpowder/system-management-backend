# FlexOper gym handover

Use this file when you give the gym the computer, not the old property-booking README.

## What they get

FlexOper on this PC: members, memberships, payments, attendance, classes, reminders, reports, trainers, expenses, and staff logins.

- Reception can run the desk.
- Admin can also manage trainers, expenses, administration, and full reports.

## Start / stop

**Every day (easiest while developing or training):**

1. Double-click `start.bat` (API on http://127.0.0.1:8000).
2. Double-click `start-frontend.bat` (app on http://localhost:5173).
3. Sign in.
4. Close both windows to stop.

**One address for the gym (after you build the frontend once):**

1. Double-click `deliver.bat` (builds the app, then serves it at http://127.0.0.1:8000).
2. Close the window to stop.

**Production process (Waitress, not Django runserver):**

1. Copy `.env.example` to `.env`.
2. Set `DJANGO_DEBUG=False` and a long `DJANGO_SECRET_KEY`.
3. Double-click `production.bat`.

If the browser shows “frontend is not built”, run `deliver.bat` or use the two-window daily start.

## Roles

| Role | What they see |
| --- | --- |
| Reception | Members, classes, memberships, payments, attendance, reminders, plans, reports, notifications |
| Admin / Super admin | Everything above, plus trainers, expenses, administration |

Create staff in **Administration** or:

```bat
venv\Scripts\activate
python manage.py createsuperuser
```

## Backup

Gym data lives in `db.sqlite3`. Copy it off this PC regularly.

- Double-click `backup.bat`, or run `python manage.py backup_database`
- Files go to the `backups` folder
- Restore: stop the app, then `python manage.py restore_database backups\homezup_YYYY-MM-DD_HH-MM.sqlite3`

Keep a copy of `backups` on a USB drive.

## Before they go live on this PC

- [ ] Site opens after a refresh (desktop and phone)
- [ ] Hamburger menu shows pages in a vertical list
- [ ] Notifications open, tap through, and close
- [ ] Add a member, take a payment, check in attendance
- [ ] Reception login cannot open trainers / expenses / administration
- [ ] Admin can open reports and export Excel/PDF
- [ ] English and French both work
- [ ] Dark and light theme both work
- [ ] `python manage.py check_delivery` passes
- [ ] At least one backup exists

## Put it on the internet later

Copy `.env.example` to `.env` and set:

- `DJANGO_DEBUG=False`
- a long random `DJANGO_SECRET_KEY` (the process will refuse to start if this is still the development default)
- your domain in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CORS_ORIGINS`
- `DJANGO_HTTPS=True` if you have HTTPS
- `DJANGO_LISTEN=127.0.0.1:8000` (put a reverse proxy in front for the public hostname)

Then:

```bat
cd frontend
npm run build
cd ..
production.bat
```

Do not use `start.bat` / `runserver` on the public internet. Logs go to `logs\flexoper.log`.

### Railway + PostgreSQL

This PC still uses `db.sqlite3` unless you set `DATABASE_URL`. On Railway:

1. Add a **PostgreSQL** database to the same project as the Django service.
2. On the Django service **Variables**, set:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (or `${{Postgres.DATABASE_PRIVATE_URL}}` for the private network)
   - `DJANGO_DEBUG` = `False`
   - `DJANGO_SECRET_KEY` = a long random value (32+ characters)
   - `DJANGO_ALLOWED_HOSTS` = your Railway domain, e.g. `your-app.up.railway.app`
   - `DJANGO_CORS_ORIGINS` = `https://your-app.up.railway.app`
3. Railway sets `PORT` and `RAILWAY_PUBLIC_DOMAIN` itself. The Docker start command migrates, then Waitress.
4. Create a staff user **inside the Docker container** (not on this PC):
   - Railway: Django service → Shell / one-off → `python manage.py createsuperuser`
   - Or: `python manage.py createsuperuser --noinput` with `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` set for that job only
   - Local Compose: `docker compose --profile tools run --rm superuser`

SQLite backup/restore commands do not apply to Railway Postgres. Use Railway’s database backups instead.

## Who to call

Fill this in before you leave the gym:

- App support: ______________________________
- Phone / WhatsApp: ______________________________
- This PC login: ______________________________
- Admin username (do not write the password here): ______________________________
