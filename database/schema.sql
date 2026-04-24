-- Enable PostGIS for map functionality (Task #6)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- =====================================================
-- 1. USERS TABLE (Email + Password Authentication)
-- =====================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'moderator', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- =====================================================
-- 2. NEIGHBORHOODS TABLE (For filtering & map)
-- =====================================================
CREATE TABLE neighborhoods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    geom GEOMETRY(POLYGON, 4326),
    center_lat DECIMAL(10, 8),
    center_lng DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_neighborhoods_geom ON neighborhoods USING GIST(geom);

-- =====================================================
-- 3. CATEGORIES TABLE (For filtering)
-- =====================================================
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    icon VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 4. SUBMISSIONS TABLE (Core content - pending moderation)
-- =====================================================
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOMETRY(POINT, 4326),
    category_id UUID REFERENCES categories(id),
    neighborhood_id UUID REFERENCES neighborhoods(id),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    moderation_notes TEXT,
    view_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_submissions_geom ON submissions USING GIST(geom);
CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_category ON submissions(category_id);
CREATE INDEX idx_submissions_neighborhood ON submissions(neighborhood_id);
CREATE INDEX idx_submissions_user ON submissions(user_id);

-- Auto-update geometry from lat/lng
CREATE OR REPLACE FUNCTION update_submission_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_submission_geom
    BEFORE INSERT OR UPDATE ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_submission_geom();

-- =====================================================
-- 5. MODERATION QUEUE (For content approval workflow)
-- =====================================================
CREATE TABLE moderation_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    moderator_id UUID REFERENCES users(id),
    action VARCHAR(50) CHECK (action IN ('approve', 'reject')),
    notes TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(submission_id)
);

CREATE INDEX idx_moderation_queue_reviewed ON moderation_queue(reviewed_at);

-- =====================================================
-- 6. SUBMISSION HISTORY (Audit log for DG2)
-- =====================================================
CREATE TABLE submission_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    changed_by UUID REFERENCES users(id),
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    notes TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_submission_history_submission ON submission_history(submission_id);

-- =====================================================
-- FUNCTIONS FOR BUSINESS LOGIC (DG2: Moderation)
-- =====================================================

-- Function to approve a submission
CREATE OR REPLACE FUNCTION approve_submission(
    p_submission_id UUID,
    p_moderator_id UUID,
    p_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE submissions 
    SET status = 'approved', 
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_submission_id;
    
    INSERT INTO moderation_queue (submission_id, moderator_id, action, notes)
    VALUES (p_submission_id, p_moderator_id, 'approve', p_notes);
    
    INSERT INTO submission_history (submission_id, changed_by, old_status, new_status, notes)
    VALUES (p_submission_id, p_moderator_id, 'pending', 'approved', p_notes);
END;
$$ LANGUAGE plpgsql;

-- Function to reject a submission
CREATE OR REPLACE FUNCTION reject_submission(
    p_submission_id UUID,
    p_moderator_id UUID,
    p_notes TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE submissions 
    SET status = 'rejected'
    WHERE id = p_submission_id;
    
    INSERT INTO moderation_queue (submission_id, moderator_id, action, notes)
    VALUES (p_submission_id, p_moderator_id, 'reject', p_notes);
    
    INSERT INTO submission_history (submission_id, changed_by, old_status, new_status, notes)
    VALUES (p_submission_id, p_moderator_id, 'pending', 'rejected', p_notes);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS FOR REPORTING (DG3: Content Quality)
-- =====================================================
CREATE VIEW vw_approved_content AS
SELECT 
    s.id,
    s.title,
    s.description,
    s.address,
    s.latitude,
    s.longitude,
    c.name AS category,
    n.name AS neighborhood,
    s.view_count,
    s.created_at
FROM submissions s
LEFT JOIN categories c ON s.category_id = c.id
LEFT JOIN neighborhoods n ON s.neighborhood_id = n.id
WHERE s.status = 'approved';

-- View for moderator dashboard (pending content)
CREATE VIEW vw_pending_moderation AS
SELECT 
    s.id,
    s.title,
    s.description,
    s.address,
    c.name AS category,
    n.name AS neighborhood,
    u.email AS submitted_by,
    s.created_at
FROM submissions s
LEFT JOIN categories c ON s.category_id = c.id
LEFT JOIN neighborhoods n ON s.neighborhood_id = n.id
LEFT JOIN users u ON s.user_id = u.id
WHERE s.status = 'pending'
ORDER BY s.created_at ASC;

-- =====================================================
-- END OF SCHEMA
-- =====================================================
