from harness.adf import adf_to_markdown


def test_paragraph_marks_and_link():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello ", "marks": [{"type": "strong"}]},
                    {
                        "type": "text",
                        "text": "world",
                        "marks": [
                            {"type": "em"},
                            {"type": "link", "attrs": {"href": "https://example.com"}},
                        ],
                    },
                ],
            }
        ],
    }
    assert adf_to_markdown(doc) == "**Hello **[*world*](https://example.com)"


def test_lists_code_and_heading():
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Steps"}]},
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Clone"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Plan"}],
                            }
                        ],
                    },
                ],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "bash"},
                "content": [{"type": "text", "text": "harness prepare ABC-1"}],
            },
        ],
    }
    text = adf_to_markdown(doc)
    assert text.startswith("## Steps")
    assert "1. Clone" in text
    assert "2. Plan" in text
    assert "```bash\nharness prepare ABC-1\n```" in text


def test_table_and_empty():
    assert adf_to_markdown(None) == ""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Repo"}],
                                    }
                                ],
                            },
                            {
                                "type": "tableHeader",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Role"}],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "frontend"}],
                                    }
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "UI"}],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ],
    }
    markdown = adf_to_markdown(doc)
    assert "| Repo | Role |" in markdown
    assert "| frontend | UI |" in markdown
