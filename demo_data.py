from datetime import datetime, timezone
from review import review_reasons

DEMO_ROWS = [
    (5, "The fitness center is spotless.", "Amenities"),
    (2, "The upstairs neighbors play music after midnight.", "Noise"),
    (1, "The bathroom sink keeps leaking.", "Maintenance"),
    (4, "The leasing team explained the renewal clearly.", "Management"),
    (5, "I feel secure entering the building at night.", "Safety"),
    (3, "The pool closes too early.", "Amenities"),
    (2, "The hallway lights keep flickering.", "Maintenance"),
    (5, "The community feels welcoming.", "General"),
    (1, "I smell gas near the basement.", "Safety"),
    (2, "The office has ignored three emails.", "Management"),
    (4, "The laundry machines work well.", "Amenities"),
    (2, "Traffic noise wakes me up.", "Noise"),
    (1, "The heating system is broken.", "Maintenance"),
    (5, "I am very happy with my apartment.", "General"),
    (3, "Parking spaces are too narrow.", "Amenities"),
    (1, "The entrance security lock is broken.", "Safety"),
    (4, "The manager handled my question professionally.", "Management"),
    (2, "The elevator is broken and I use a wheelchair.", "Maintenance"),
    (5, "The neighbors are quiet and respectful.", "Noise"),
    (1, "The apartment looks wonderful.", "General"),
]


def seed_demo_data(connection):
    existing = connection.execute(
        "SELECT COUNT(*) FROM feedback WHERE is_demo = 1"
    ).fetchone()[0]

    if existing:
        return 0

    for rating, comment, topic in DEMO_ROWS:
        reasons = review_reasons(comment, rating, topic)

        connection.execute(
            """
            INSERT INTO feedback (
                timestamp, rating, comment, topic,
                classification_error, needs_review,
                review_reason, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                rating,
                comment,
                topic,
                None,
                int(bool(reasons)),
                "; ".join(reasons),
            )
        )

    return len(DEMO_ROWS)
