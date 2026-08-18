from sklearn.feature_extraction.text import TfidfVectorizer


def analyze_keywords(profile_text: str, jd_text: str) -> dict:
    """TF-IDF keyword gap analysis between profile text and job description.

    Returns matched_keywords, missing_keywords (each a list of {keyword, score} dicts)
    and keyword_score (0-100 integer match rate).
    """
    profile_lower = profile_text.lower().strip()
    jd_lower = jd_text.lower().strip()

    if not profile_lower or not jd_lower:
        return {"matched_keywords": [], "missing_keywords": [], "keyword_score": 0}

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        lowercase=True,
        min_df=1,
    )

    try:
        matrix = vectorizer.fit_transform([profile_lower, jd_lower])
    except ValueError:
        return {"matched_keywords": [], "missing_keywords": [], "keyword_score": 0}

    feature_names = vectorizer.get_feature_names_out()
    jd_scores = matrix[1].toarray()[0]

    # Top JD terms sorted by TF-IDF score descending (most distinctive first)
    sorted_indices = jd_scores.argsort()[::-1]
    top_terms = [
        (feature_names[i], float(jd_scores[i]))
        for i in sorted_indices[:30]
        if jd_scores[i] > 0
    ]

    matched: list[dict] = []
    missing: list[dict] = []
    for term, score in top_terms:
        entry = {"keyword": term, "score": round(score, 3)}
        if term in profile_lower:
            matched.append(entry)
        else:
            missing.append(entry)

    total = len(matched) + len(missing)
    keyword_score = int(len(matched) / max(total, 1) * 100)

    return {
        "matched_keywords": matched,
        "missing_keywords": missing,
        "keyword_score": keyword_score,
    }
