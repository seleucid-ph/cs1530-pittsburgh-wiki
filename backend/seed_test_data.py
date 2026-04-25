import os
import psycopg2

conn = psycopg2.connect(
    os.environ.get("DATABASE_URL", "postgresql://localhost/pittsburgh_wiki")
)
cur = conn.cursor()

# need a real user row so the foreign key on submissions doesn't blow up,
# in production this would come from Aneesha's signup endpoint
cur.execute("""
    INSERT INTO users (email, password_hash, full_name, role)
    VALUES ('seed@test.local', 'not_a_real_hash', 'Seed User', 'moderator')
    ON CONFLICT (email) DO NOTHING
    RETURNING id;
""")
row = cur.fetchone()
if row:
    user_id = row[0]
else:
    cur.execute("SELECT id FROM users WHERE email = 'seed@test.local';")
    user_id = cur.fetchone()[0]

# seed the neighborhood and category lookup tables that submissions reference
neighborhoods = [
    "Downtown", "Oakland", "Shadyside", "Squirrel Hill", "Lawrenceville",
    "Strip District", "North Shore", "South Side", "Mount Washington",
    "East Liberty", "Bloomfield", "Polish Hill"
]
for name in neighborhoods:
    cur.execute("""
        INSERT INTO neighborhoods (name) VALUES (%s)
        ON CONFLICT (name) DO NOTHING;
    """, (name,))

categories = ["landmark", "nature", "food", "culture", "history"]
for name in categories:
    cur.execute("""
        INSERT INTO categories (name) VALUES (%s)
        ON CONFLICT (name) DO NOTHING;
    """, (name,))

# each tuple is (title, neighborhood, category, description, lat, lng)
submissions = [
    (
        "Point State Park",
        "Downtown", "landmark",
        "Historic park at the confluence of Pittsburgh's three rivers, site of Fort Duquesne.",
        40.4424, -80.0145
    ),
    (
        "Phipps Conservatory",
        "Oakland", "nature",
        "Victorian glasshouse and botanical gardens opened in 1893, one of the most sustainable buildings in the world.",
        40.4388, -79.9495
    ),
    (
        "Primanti Brothers",
        "Strip District", "food",
        "Pittsburgh institution famous for sandwiches stuffed with fries and coleslaw, open since 1933.",
        40.4480, -79.9723
    ),
    (
        "Carnegie Museum of Natural History",
        "Oakland", "culture",
        "One of the top natural history museums in the US, home to an extensive dinosaur fossil collection.",
        40.4432, -79.9502
    ),
    (
        "Fort Pitt Museum",
        "Downtown", "history",
        "Museum inside a reconstructed bastion of Fort Pitt covering the French and Indian War era.",
        40.4418, -80.0138
    ),
    (
        "Duquesne Incline",
        "Mount Washington", "landmark",
        "Historic cable car dating to 1877 offering a panoramic view of downtown Pittsburgh.",
        40.4295, -80.0233
    ),
    (
        "Schenley Park",
        "Oakland", "nature",
        "456-acre public park with trails, a public pool, ice skating rink, and Panther Hollow Lake.",
        40.4353, -79.9456
    ),
    (
        "Andy Warhol Museum",
        "North Shore", "culture",
        "The largest museum in the US dedicated to a single artist, covering Warhol's life and work across seven floors.",
        40.4480, -80.0013
    ),
]

approved = 0
for title, neighborhood_name, category_name, description, lat, lng in submissions:

    cur.execute("SELECT id FROM neighborhoods WHERE name = %s;", (neighborhood_name,))
    neighborhood_id = cur.fetchone()[0]

    cur.execute("SELECT id FROM categories WHERE name = %s;", (category_name,))
    category_id = cur.fetchone()[0]

    # insert as pending first, same as what Aaron's POST /api/submissions will do.
    # the geom column gets populated automatically by James's trigger on insert.
    cur.execute("""
        INSERT INTO submissions
            (title, description, latitude, longitude, category_id, neighborhood_id, user_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        RETURNING id;
    """, (title, description, lat, lng, category_id, neighborhood_id, user_id))
    submission_id = cur.fetchone()[0]

    # approve it using James's stored procedure, same as what the moderation endpoint will call
    cur.execute("SELECT approve_submission(%s, %s, %s);",
                (submission_id, user_id, 'seeded for local dev'))

    approved += 1

conn.commit()
cur.close()
conn.close()

print(f"Seeded {approved} entries through the submission flow.")
