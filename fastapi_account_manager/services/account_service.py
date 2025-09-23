import re
import unicodedata

USERNAME_RE = re.compile(r"^[a-z0-9._-]+$")  # ascii lowercase digits . _ -

def to_ascii_slug(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

def ensure_ascii_username(s: str):
    slug = to_ascii_slug(s)
    if slug != s or not USERNAME_RE.match(slug):
        raise ValueError("Username must be ASCII (no accents), allowed: [a-z0-9._-]")

def build_username(company_code: str, raw_username: str) -> str:
    slug = to_ascii_slug(raw_username)
    if not USERNAME_RE.match(slug):
        raise ValueError("Invalid username format")
    prefix = (company_code or "").strip().lower()
    if prefix and not slug.startswith(prefix + "."):
        return f"{prefix}.{slug}"
    return slug
