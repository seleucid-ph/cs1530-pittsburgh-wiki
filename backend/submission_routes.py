"""
submission_routes.py — Content submission & moderation queue.

Register in wiki.py with:
    from backend.submission_routes import submission_bp
    app.register_blueprint(submission_bp)

Endpoints
---------
POST /api/submissions              – create a new pending submission
GET  /api/moderation/pending       – list all pending submissions
POST /api/moderation/<id>/approve  – approve a submission (creates page + entry)
POST /api/moderation/<id>/reject   – reject a submission
"""

import os
import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request

submission_bp = Blueprint("submissions", __name__)

# ── Default coordinates (Pittsburgh city center) ────────────────────
# Used when the frontend doesn't send lat/lng so the NOT NULL
# constraint on submissions.location is satisfied.
DEFAULT_LNG = -79.9959
DEFAULT_LAT = 40.4406


def get_db():
    """Return a new psycopg2 connection using the same env var as map_routes."""
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/pittsburgh_wiki"
    )
    return psycopg2.connect(db_url)


# ── POST /api/submissions ───────────────────────────────────────────
@submission_bp.route("/api/submissions", methods=["POST"])
def create_submission():
    """
    Accepts JSON:
        {
            "title":        "Point State Park",
            "description":  "Historic park at …",
            "neighborhood": "Downtown",
            "category":     "landmark",
            "submitted_by": "seed_user",
            "lat":          40.4424,          # optional
            "lng":          -80.0145          # optional
        }
    Creates a row in submissions with status='pending'.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    description  = (data.get("description") or "").strip()
    neighborhood = (data.get("neighborhood") or "").strip() or None
    category     = (data.get("category") or "").strip() or None
    submitted_by = (data.get("submitted_by") or "").strip() or None

    # Coordinates are optional; default to Pittsburgh center.
    try:
        lng = float(data["lng"]) if "lng" in data else DEFAULT_LNG
        lat = float(data["lat"]) if "lat" in data else DEFAULT_LAT
    except (ValueError, TypeError):
        return jsonify({"error": "lat and lng must be numbers"}), 400

    # Look up the user_id if submitted_by was provided.
    user_id = None
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if submitted_by:
                cur.execute(
                    "SELECT id FROM users WHERE username = %s;",
                    (submitted_by,),
                )
                row = cur.fetchone()
                if row:
                    user_id = row[0]

            cur.execute(
                """
                INSERT INTO submissions
                    (user_id, title, neighborhood, category, excerpt, location, status)
                VALUES (
                    %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    'pending'
                )
                RETURNING id, title, neighborhood, category, excerpt, status;
                """,
                (user_id, title, neighborhood, category, description, lng, lat),
            )
            new = cur.fetchone()
            conn.commit()

        return jsonify({
            "id":           new[0],
            "title":        new[1],
            "neighborhood": new[2],
            "category":     new[3],
            "description":  new[4],
            "status":       new[5],
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()


# ── GET /api/moderation/pending ─────────────────────────────────────
@submission_bp.route("/api/moderation/pending", methods=["GET"])
def list_pending():
    """Return every submission whose status is 'pending'."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, title, neighborhood, category,
                       excerpt AS description, status,
                       ST_Y(location::geometry) AS lat,
                       ST_X(location::geometry) AS lng
                FROM submissions
                WHERE status = 'pending'
                ORDER BY id;
                """
            )
            rows = cur.fetchall()

        return jsonify([dict(r) for r in rows])

    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()


# ── POST /api/moderation/<id>/approve ───────────────────────────────
@submission_bp.route("/api/moderation/<int:sub_id>/approve", methods=["POST"])
def approve_submission(sub_id):
    """
    1. Verify the submission exists and is still pending.
    2. Create a pages row (so entries.page_id has something to reference).
    3. Copy the submission into entries with status='approved'.
    4. Flip the submission's own status to 'approved'.
    """
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch the pending submission.
            cur.execute(
                "SELECT * FROM submissions WHERE id = %s;", (sub_id,)
            )
            sub = cur.fetchone()

            if not sub:
                return jsonify({"error": "Submission not found"}), 404
            if sub["status"] != "pending":
                return jsonify({
                    "error": f"Submission already {sub['status']}"
                }), 409

            # Create a page stub.
            cur.execute(
                """
                INSERT INTO pages (title, content, neighborhood, category)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (sub["title"], sub["excerpt"], sub["neighborhood"], sub["category"]),
            )
            page_id = cur.fetchone()["id"]

            # Insert into entries.
            cur.execute(
                """
                INSERT INTO entries
                    (page_id, title, neighborhood, category, excerpt, location, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'approved')
                RETURNING id;
                """,
                (
                    page_id,
                    sub["title"],
                    sub["neighborhood"],
                    sub["category"],
                    sub["excerpt"],
                    sub["location"],
                ),
            )
            entry_id = cur.fetchone()["id"]

            # Mark the submission as approved.
            cur.execute(
                """
                UPDATE submissions
                SET status = 'approved', reviewed_at = NOW()
                WHERE id = %s;
                """,
                (sub_id,),
            )
            conn.commit()

        return jsonify({
            "submission_id": sub_id,
            "entry_id":      entry_id,
            "page_id":       page_id,
            "status":        "approved",
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()


# ── POST /api/moderation/<id>/reject ────────────────────────────────
@submission_bp.route("/api/moderation/<int:sub_id>/reject", methods=["POST"])
def reject_submission(sub_id):
    """Flip a pending submission to 'rejected'."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, status FROM submissions WHERE id = %s;", (sub_id,)
            )
            sub = cur.fetchone()

            if not sub:
                return jsonify({"error": "Submission not found"}), 404
            if sub["status"] != "pending":
                return jsonify({
                    "error": f"Submission already {sub['status']}"
                }), 409

            cur.execute(
                """
                UPDATE submissions
                SET status = 'rejected', reviewed_at = NOW()
                WHERE id = %s
                RETURNING id, status;
                """,
                (sub_id,),
            )
            updated = cur.fetchone()
            conn.commit()

        return jsonify({
            "submission_id": updated["id"],
            "status":        updated["status"],
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()
