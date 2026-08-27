from harness.routing import recommend_workspace, score_workspace


def test_scores_project_component_and_keywords(catalog):
    issue = {
        "project": {"key": "WEB"},
        "components": ["Frontend"],
        "labels": ["ui"],
        "summary": "Fix the checkout button color",
        "description": "The css is wrong",
        "issue_type": "Bug",
    }
    workspace = catalog.workspace("frontend")
    score, reasons = score_workspace(workspace, issue)
    assert score >= 5 + 4 + 3 + 2
    assert any("project WEB" in reason for reason in reasons)
    assert any("button" in reason for reason in reasons)


def test_fallback_when_nothing_matches(catalog):
    issue = {
        "project": {"key": "OPS"},
        "components": [],
        "labels": [],
        "summary": "Rotate logs",
        "description": "",
    }
    recommended, alternatives = recommend_workspace(catalog, issue)
    assert recommended is not None
    assert recommended["id"] == "backend"
    assert "fallback workspace" in recommended["reasons"]
    assert {item["id"] for item in alternatives} == {"frontend"}


def test_prefers_higher_score_over_fallback(catalog):
    issue = {
        "project": {"key": "WEB"},
        "components": [],
        "labels": [],
        "summary": "New page",
        "description": "",
    }
    recommended, _ = recommend_workspace(catalog, issue)
    assert recommended is not None
    assert recommended["id"] == "frontend"
    assert recommended["score"] > 0
