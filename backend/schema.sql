CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_moderator  BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- pages are the public wiki articles that entries point back to
CREATE TABLE IF NOT EXISTS pages (
    id           SERIAL PRIMARY KEY,
    title        VARCHAR(255) NOT NULL,
    content      TEXT,
    neighborhood VARCHAR(100),
    category     VARCHAR(50),
    created_by   INTEGER REFERENCES users(id),
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- submissions sit here waiting for a moderator to approve or reject them
CREATE TABLE IF NOT EXISTS submissions (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    title        VARCHAR(255) NOT NULL,
    neighborhood VARCHAR(100),
    category     VARCHAR(50),
    excerpt      TEXT,
    content      TEXT,
    lng          FLOAT,
    lat          FLOAT,
    status       VARCHAR(20) DEFAULT 'pending',
    reviewed_by  INTEGER REFERENCES users(id),  -- tracks which moderator acted on it
    submitted_at TIMESTAMP DEFAULT NOW(),
    reviewed_at  TIMESTAMP
);

-- entries are submissions that got approved and are ready to show on the map
CREATE TABLE IF NOT EXISTS entries (
    id           SERIAL PRIMARY KEY,
    page_id      INTEGER REFERENCES pages(id),
    title        VARCHAR(255) NOT NULL,
    neighborhood VARCHAR(100),
    category     VARCHAR(50),
    excerpt      TEXT,
    location     GEOGRAPHY(POINT, 4326),
    status       VARCHAR(20) DEFAULT 'approved',
    created_at   TIMESTAMP DEFAULT NOW()
);

-- GiST index is what makes the PostGIS ST_Within queries fast enough to use
CREATE INDEX IF NOT EXISTS idx_entries_location ON entries USING GIST(location);

-- these let the search and filter endpoints skip full table scans
CREATE INDEX IF NOT EXISTS idx_entries_neighborhood ON entries(neighborhood);
CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);

-- GIN index for full text search across title and excerpt so GET /api/search doesn't crawl
CREATE INDEX IF NOT EXISTS idx_entries_fts ON entries
    USING GIN(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(excerpt, '')));
