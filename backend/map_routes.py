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

# Same boundary as PGH_BOUNDS but as a WKT polygon string for ST_GeomFromText.
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
    # neighborhood and category are now names we look up against James's
    # neighborhoods and categories tables rather than plain string columns
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

    # James's schema stores approved content in submissions with status='approved'.
    # We join categories and neighborhoods to get their names for the frontend,
    # and use the trigger-maintained geom column for the spatial query.
    # ST_Y/ST_X need the ::geometry cast because they don't accept GEOGRAPHY directly.
    sql = """
        SELECT
            s.id,
            s.title,
            s.description AS excerpt,
            c.name  AS category,
            n.name  AS neighborhood,
            s.latitude  AS lat,
            s.longitude AS lng
        FROM submissions s
        LEFT JOIN categories    c ON s.category_id    = c.id
        LEFT JOIN neighborhoods n ON s.neighborhood_id = n.id
        WHERE
            s.status = 'approved'
            AND s.geom IS NOT NULL
            AND ST_Within(s.geom, ST_GeomFromText(%s, 4326))
    """
    params = [viewport_wkt]

    if neighborhood:
        sql += " AND n.name = %s"
        params.append(neighborhood)

    if category:
        sql += " AND c.name = %s"
        params.append(category)

    if keyword:
        sql += " AND (s.title ILIKE %s OR s.description ILIKE %s)"
        like = f"%{keyword}%"
        params.extend([like, like])

    sql += " ORDER BY s.title LIMIT 500;"

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
    """Returns neighborhoods that have approved submissions, used to populate the sidebar dropdown."""
    sql = """
        SELECT DISTINCT n.name
        FROM neighborhoods n
        JOIN submissions s ON s.neighborhood_id = n.id
        WHERE s.status = 'approved'
          AND s.geom IS NOT NULL
          AND ST_Within(s.geom, ST_GeomFromText(%s, 4326))
        ORDER BY n.name;
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
