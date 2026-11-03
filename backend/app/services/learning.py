"""Learning help when no curated resource exists: a search phrase the user can paste into a
search engine or course site. Deterministic and link-free (we never invent URLs)."""

CREDENTIALS = {"license", "certification"}


def search_phrase(skill_name: str, category: str) -> str:
    """'Phlebotomy free course', 'Plumbing License how to get', 'Empathy at work'..."""
    name = " ".join(skill_name.split())
    if category in CREDENTIALS:
        return f"{name} requirements how to apply"
    if category == "soft_skill":
        return f"how to improve {name.lower()} at work free course"
    return f"{name} free course for beginners"
