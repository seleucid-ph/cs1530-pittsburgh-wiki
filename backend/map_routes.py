
"""
map_routes.py, register in wiki.py with:
    from map_routes import map_bp
    app.register_blueprint(map_bp)

Expects James's entries table to have a GEOGRAPHY(POINT, 4326) column named 'location'
with a GiST index:  CREATE INDEX ON entries USING GIST(location);
"""

import os
import psycopg2
import psycopg2.extras
from flask import Blueprint, render_template, jsonify, request

map_bp = Blueprint('map', __name__)

# Hard city boundary, used to clamp any incoming viewport params so we never
# serve or accept coordinates outside Pittsburgh.
PGH_BOUNDS = {
    "min_lat":  40.3617, "max_lat":  40.5011,
    "min_lng": -80.0952, "max_lng": -79.8650,
}

# Same boundary as PGH_BOUNDS but as a WKT polygon string so we can pass it directly to ST_GeomFromText.
PGH_POLYGON_WKT = (
    "POLYGON((-80.0952 40.3617, -79.8650 40.3617, "
    "-79.8650 40.5011, -80.0952 40.5011, -80.0952 40.3617))"
)


def get_db():
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost/pittsburgh_wiki")
    return psycopg2.connect(db_url)


@map_bp.route("/map")
def map_page():
    return render_template("map.html")


@map_bp.route("/api/map")
def api_map():
    neighborhood = request.args.get("neighborhood", "").strip()
    category     = request.args.get("category",     "").strip()
    keyword      = request.args.get("q",            "").strip()

    # The frontend can optionally send the current viewport bbox on pan/zoom.
    # We fall back to full Pittsburgh bounds if it's not included.
    try:
        vp_min_lat = float(request.args.get("min_lat", PGH_BOUNDS["min_lat"]))
        vp_max_lat = float(request.args.get("max_lat", PGH_BOUNDS["max_lat"]))
        vp_min_lng = float(request.args.get("min_lng", PGH_BOUNDS["min_lng"]))
        vp_max_lng = float(request.args.get("max_lng", PGH_BOUNDS["max_lng"]))
    except ValueError:
        return jsonify({"error": "Invalid bounding box parameters"}), 400

    # Clamp to city bounds so a manipulated request can't pull data from outside Pittsburgh.
    vp_min_lat = max(vp_min_lat, PGH_BOUNDS["min_lat"])
    vp_max_lat = min(vp_max_lat, PGH_BOUNDS["max_lat"])
    vp_min_lng = max(vp_min_lng, PGH_BOUNDS["min_lng"])
    vp_max_lng = min(vp_max_lng, PGH_BOUNDS["max_lng"])

    # Build a WKT polygon from the (possibly clamped) viewport so we can pass it to ST_Within.
    viewport_wkt = (
        f"POLYGON(({vp_min_lng} {vp_min_lat}, {vp_max_lng} {vp_min_lat}, "
        f"{vp_max_lng} {vp_max_lat}, {vp_min_lng} {vp_max_lat}, "
        f"{vp_min_lng} {vp_min_lat}))"
    )

    # ST_Y/ST_X pull lat/lng out of the GEOGRAPHY column as plain floats for the JSON response.
    # The ::geometry cast is needed because ST_Y/ST_X don't accept GEOGRAPHY directly.
    sql = """
        SELECT
            e.id, e.page_id, e.title, e.neighborhood, e.category, e.excerpt,
            ST_Y(e.location::geometry) AS lat,
            ST_X(e.location::geometry) AS lng
        FROM entries e
        WHERE
            e.status = 'approved'
            AND e.location IS NOT NULL
            AND ST_Within(e.location::geometry, ST_GeomFromText(%s, 4326))
    """
    params = [viewport_wkt]

    if neighborhood:
        sql += " AND e.neighborhood = %s"
        params.append(neighborhood)

    if category:
        sql += " AND e.category = %s"
        params.append(category)

    if keyword:
        sql += " AND (e.title ILIKE %s OR e.excerpt ILIKE %s)"
        like = f"%{keyword}%"
        params.extend([like, like])

    sql += " ORDER BY e.title LIMIT 500;"

    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    return jsonify([dict(row) for row in rows])


@map_bp.route("/api/neighborhoods")
def api_neighborhoods():
    """Returns neighborhoods that have approved, located entries, used to populate the sidebar dropdown."""
    sql = """
        SELECT DISTINCT neighborhood
        FROM entries
        WHERE status = 'approved'
          AND neighborhood IS NOT NULL
          AND location IS NOT NULL
          AND ST_Within(location::geometry, ST_GeomFromText(%s, 4326))
        ORDER BY neighborhood;
    """
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(sql, [PGH_POLYGON_WKT])
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify([r[0] for r in rows])
