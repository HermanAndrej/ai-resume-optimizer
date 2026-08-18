from backend.services.keyword_analyzer import analyze_keywords


def test_missing_keywords_detected():
    profile = "Python developer with 5 years of ML experience"
    jd = "Looking for Python developer with AWS and Kubernetes"
    result = analyze_keywords(profile, jd)
    missing = [k["keyword"] for k in result["missing_keywords"]]
    assert "aws" in missing
    assert "kubernetes" in missing


def test_matched_keywords():
    profile = "Python developer"
    jd = "Python developer needed"
    result = analyze_keywords(profile, jd)
    assert result["keyword_score"] > 50
    matched = [k["keyword"] for k in result["matched_keywords"]]
    assert "python" in matched


def test_empty_inputs():
    result = analyze_keywords("", "some job description")
    assert result["keyword_score"] == 0
    assert result["matched_keywords"] == []
    assert result["missing_keywords"] == []


def test_result_structure():
    result = analyze_keywords("Python developer", "Looking for a Python engineer")
    assert "matched_keywords" in result
    assert "missing_keywords" in result
    assert "keyword_score" in result
    assert isinstance(result["keyword_score"], int)
    assert 0 <= result["keyword_score"] <= 100
