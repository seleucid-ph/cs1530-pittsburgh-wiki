# cs1530-pittsburgh-wiki

A community wiki for Pittsburgh neighborhoods and points of interest. Users can sign up, browse an interactive map of geo-located entries across the city, and submit their own content for moderator review. Built for CS1530 as a full-stack Flask + PostGIS application.

## Tech Stack

- **Backend:** Flask, psycopg2, Werkzeug (password hashing)
- **Database:** PostgreSQL with PostGIS for spatial queries
- **Frontend:** Leaflet.js, Leaflet.markercluster, vanilla JS
- **Auth:** Flask sessions

## Project Structure

```
cs1530-pittsburgh-wiki/
├── wiki.py                          main Flask app, registers all blueprints
├── requirements.txt
├── database/
│   └── schema.sql                   full database schema including PostGIS setup
├── backend/
│   ├── map_routes.py                /map page and /api/map, /api/neighborhoods endpoints
│   ├── auth_routes.py               /api/auth/signup, /api/auth/login, /api/auth/logout
│   └── seed_test_data.py            populates DB with sample Pittsburgh entries for local dev
├── frontend/
│   └── static/
│       └── js/
│           └── api.js               all fetch calls to the Flask backend
└── templates/
    ├── welcome-page.html            landing page with login/signup links
    ├── login.html
    ├── signup.html
    ├── home.html                    post-login landing page
    └── map.html                     interactive Pittsburgh map
```

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL with PostGIS extension (`sudo pacman -S postgis` on Arch, `sudo apt install postgresql-postgis` on Ubuntu)

### First time setup

```bash
# initialize and start postgres
sudo -u postgres initdb --locale=C.UTF-8 --encoding=UTF8 -D /var/lib/postgres/data
sudo systemctl start postgresql

# create a user and database
sudo -u postgres createuser --superuser $(whoami)
sudo -u postgres createdb pittsburgh_wiki

# run the schema
psql -d pittsburgh_wiki -f database/schema.sql

# install python dependencies
pip install -r requirements.txt

# seed test data
python backend/seed_test_data.py
```

### Running the app

```bash
flask --app wiki.py run
```

Then open http://localhost:5000

### Re-seeding

If you need to wipe and re-seed the database:

```bash
psql -d pittsburgh_wiki -c "DROP TABLE IF EXISTS submission_history, moderation_queue, submissions, categories, neighborhoods, users CASCADE;"
psql -d pittsburgh_wiki -f database/schema.sql
python backend/seed_test_data.py
```

### Environment variables

By default the app connects to `postgresql://localhost/pittsburgh_wiki` using your system username. To override:

```bash
export DATABASE_URL=postgresql://user:password@host/dbname
```

## Features

**Interactive Map** — Leaflet.js map locked to Pittsburgh bounds with marker clustering, sidebar search, category filter chips, and neighborhood dropdown. Queries approved submissions from PostGIS via `/api/map`.

**Login / Signup** — Email and password auth with Werkzeug password hashing. Sessions managed server-side via Flask. Redirects to `/home` on success.

**Database Schema** — PostgreSQL + PostGIS schema with users, neighborhoods, categories, submissions, moderation queue, and submission history tables. Includes a trigger that auto-generates PostGIS geometry from lat/lng on insert, and stored procedures for approving and rejecting submissions.

**Frontend API Layer** — Centralized `api.js` with fetch wrappers for all endpoints covering map, pages, search, auth, submissions, and moderation.

**Test Data Seed** — Seeds 8 real Pittsburgh locations by going through the full submission and moderation flow so local dev matches production behavior.

## Team

| Member | Role | Contribution |
|--------|------|--------------|
| June | PO | Repository setup, branching model |
| James | Dev | Database schema and PostGIS setup |
| Aneesha | SM | Login/signup auth service and templates |
| Khuslen | Dev | Frontend API layer |
| Aaron | Dev | Content submission backend |
| Zachary | Dev | Interactive map UI and PostGIS map endpoints |
