import os
import psycopg2

conn = psycopg2.connect(
    os.environ.get("DATABASE_URL", "postgresql://localhost/pittsburgh_wiki")
)
cur = conn.cursor()

# need a real user row so the foreign key on submissions doesn't blow up,
# in production this would come from Aneesha's signup endpoint
cur.execute("""
    INSERT INTO users (username, email, password_hash)
    VALUES ('seed_user', 'seed@test.local', 'not_a_real_hash')
    ON CONFLICT (username) DO NOTHING
    RETURNING id;
""")
row = cur.fetchone()
if row:
    user_id = row[0]
else:
    cur.execute("SELECT id FROM users WHERE username = 'seed_user';")
    user_id = cur.fetchone()[0]

# Each tuple is (title, neighborhood, category, excerpt, lng, lat).
# lng comes first in ST_MakePoint because PostGIS treats coordinates as (x, y) not (lat, lng).
submissions = [
    (
        "Point State Park",
        "Downtown",
        "landmark",
        "Historic park at the confluence of Pittsburgh's three rivers, site of Fort Duquesne.",
        -80.0145, 40.4424
    ),
    (
        "Phipps Conservatory",
        "Oakland",
        "nature",
        "Victorian glasshouse and botanical gardens opened in 1893, one of the most sustainable buildings in the world.",
        -79.9495, 40.4388
    ),
    (
        "Primanti Brothers",
        "Strip District",
        "food",
        "Pittsburgh institution famous for sandwiches stuffed with fries and coleslaw, open since 1933.",
        -79.9723, 40.4480
    ),
    (
        "Carnegie Museum of Natural History",
        "Oakland",
        "culture",
        "One of the top natural history museums in the US, home to an extensive dinosaur fossil collection.",
        -79.9502, 40.4432
    ),
    (
        "Fort Pitt Museum",
        "Downtown",
        "history",
        "Museum inside a reconstructed bastion of Fort Pitt covering the French and Indian War era.",
        -80.0138, 40.4418
    ),
    (
        "Duquesne Incline",
        "Mount Washington",
        "landmark",
        "Historic cable car dating to 1877 offering a panoramic view of downtown Pittsburgh.",
        -80.0233, 40.4295
    ),
    (
        "Schenley Park",
        "Oakland",
        "nature",
        "456-acre public park with trails, a public pool, ice skating rink, and Panther Hollow Lake.",
        -79.9456, 40.4353
    ),
    (
        "Andy Warhol Museum",
        "North Shore",
        "culture",
        "The largest museum in the US dedicated to a single artist, covering Warhol's life and work across seven floors.",
        -80.0013, 40.4480
    ),
]

approved = 0
for title, neighborhood, category, excerpt, lng, lat in submissions:

    # insert as pending first, same as what Aaron's POST /api/submissions will do
    cur.execute("""
        INSERT INTO submissions (user_id, title, neighborhood, category, excerpt, location, status)
        VALUES (
            %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            'pending'
        )
        RETURNING id;
    """, (user_id, title, neighborhood, category, excerpt, lng, lat))
    submission_id = cur.fetchone()[0]

    # create the page so entries has something to reference
    cur.execute("""
        INSERT INTO pages (title) VALUES (%s) RETURNING id;
    """, (title,))
    page_id = cur.fetchone()[0]

    # approve into entries, same as what the moderation approve endpoint will do
    # the ::geography cast is needed so ST_Within in map_routes.py works
    cur.execute("""
        INSERT INTO entries (page_id, title, neighborhood, category, excerpt, location, status)
        VALUES (
            %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            'approved'
        );
    """, (page_id, title, neighborhood, category, excerpt, lng, lat))

    # flip the submission to approved so the moderation queue stays consistent
    cur.execute("""
        UPDATE submissions SET status = 'approved' WHERE id = %s;
    """, (submission_id,))

    approved += 1

conn.commit()
cur.close()
conn.close()

print(f"Seeded {approved} entries through the submission flow.")
