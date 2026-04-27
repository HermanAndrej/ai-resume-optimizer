import sqlite3

from sklearn.feature_extraction.text import TfidfVectorizer

from backend.models import KeywordOverlap

PROFILE_ID = 1


def flatten_profile(conn: sqlite3.Connection) -> str:
    parts: list[str] = []

    row = conn.execute(
        "SELECT summary FROM profile WHERE id = ?", (PROFILE_ID,)
    ).fetchone()
    if row and row["summary"]:
        parts.append(row["summary"])

    exp_rows = conn.execute(
        "SELECT id, description FROM experience WHERE profile_id = ?", (PROFILE_ID,)
    ).fetchall()
    for exp in exp_rows:
        if exp["description"]:
            parts.append(exp["description"])
        bullets = conn.execute(
            "SELECT text FROM experience_bullets WHERE experience_id = ?", (exp["id"],)
        ).fetchall()
        for b in bullets:
            if b["text"]:
                parts.append(b["text"])

    skill_rows = conn.execute(
        "SELECT skill FROM skills WHERE profile_id = ?", (PROFILE_ID,)
    ).fetchall()
    for r in skill_rows:
        if r["skill"]:
            parts.append(r["skill"])

    proj_rows = conn.execute(
        "SELECT description, tech_stack, bullets FROM projects WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchall()
    for p in proj_rows:
        for field in ("description", "tech_stack", "bullets"):
            if p[field]:
                parts.append(p[field])

    edu_rows = conn.execute(
        "SELECT highlights FROM education WHERE profile_id = ?", (PROFILE_ID,)
    ).fetchall()
    for e in edu_rows:
        if e["highlights"]:
            parts.append(e["highlights"])

    return " ".join(parts)


def extract_keywords(text: str, top_k: int = 30) -> list[tuple[str, float]]:
    if not text or not text.strip():
        return []
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_features=200,
    )
    tfidf_matrix = vectorizer.fit_transform([text])
    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.toarray()[0]
    ranked = sorted(
        zip(feature_names, scores), key=lambda x: x[1], reverse=True
    )
    return [(term, float(score)) for term, score in ranked[:top_k] if score > 0]


def compute_overlap(jd_text: str, profile_text: str) -> KeywordOverlap:
    jd_keywords = {term for term, _ in extract_keywords(jd_text, top_k=50)}
    profile_keywords = {term for term, _ in extract_keywords(profile_text, top_k=50)}

    if not jd_keywords:
        return KeywordOverlap(matched=[], missing=[], jd_only=[], match_pct=0.0)

    matched = sorted(jd_keywords & profile_keywords)
    missing = sorted(jd_keywords - profile_keywords)
    jd_only = sorted(jd_keywords - profile_keywords)
    match_pct = round(len(matched) / len(jd_keywords) * 100, 1)

    return KeywordOverlap(
        matched=matched,
        missing=missing,
        jd_only=jd_only,
        match_pct=match_pct,
    )
