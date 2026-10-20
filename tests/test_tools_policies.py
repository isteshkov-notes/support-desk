import pytest

from supportdesk.tools import ToolContext, ToolRegistry
from supportdesk.tools.policies import stem, tokenize


def hits(registry: ToolRegistry, ctx: ToolContext, query: str, top_k: int = 3) -> list[str]:
    result = registry.run(ctx, "search_policies", {"query": query, "top_k": top_k})
    assert not result.is_error
    results = result.content["results"]
    assert isinstance(results, list)
    return [str(h["citation"]) for h in results if isinstance(h, dict)]


# Go:
#   func hits(t *testing.T, reg *ToolRegistry, ctx ToolContext, q string, k int) []string {
#       t.Helper()
#       ...
#   }
# A plain helper function (not a fixture) with a default argument (top_k=3) - Go has no
# default args; you'd write a second function or an options struct.


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        pytest.param(
            "do I keep loyalty points on a refunded order", "POL-LOYALTY §2", id="loyalty"
        ),
        pytest.param("my package is lost, no tracking movement", "POL-SHIPPING §3", id="lost"),
        pytest.param("damaged item photo", "POL-DAMAGED §1", id="damaged"),
        pytest.param("can you share my husband's order details", "POL-SECURITY §2", id="privacy"),
    ],
)
def test_finds_the_relevant_section(
    registry: ToolRegistry, ctx: ToolContext, query: str, expected: str
) -> None:
    assert expected in hits(registry, ctx, query)


# Go: table-driven test with t.Run(tc.name, ...). These are smoke checks for the naive
# search; week 4 turns this into a real Recall@5 measurement over 20 questions.


def test_results_are_ranked_and_limited(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "search_policies", {"query": "refund order", "top_k": 2})

    results = result.content["results"]
    assert isinstance(results, list)
    assert len(results) == 2
    scores = [h["score"] for h in results if isinstance(h, dict)]
    assert scores == sorted(scores, key=lambda s: -int(str(s)))


def test_no_match_is_an_empty_result_not_an_error(registry: ToolRegistry, ctx: ToolContext) -> None:
    result = registry.run(ctx, "search_policies", {"query": "bitcoin crypto wallet"})

    assert not result.is_error
    assert result.content["results"] == []


@pytest.mark.parametrize("top_k", [0, 11])
def test_top_k_is_bounded(registry: ToolRegistry, ctx: ToolContext, top_k: int) -> None:
    result = registry.run(ctx, "search_policies", {"query": "refund", "top_k": top_k})

    assert result.content["error"] == "invalid_input"


# parametrize with a single argument name takes a plain list of values; ids are
# generated automatically (top_k0, top_k1).


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("damaged", "damag"),
        ("damage", "damag"),
        ("refunds", "refund"),
        ("shipping", "shipp"),
        ("days", "days"),
        ("item", "item"),
    ],
)
def test_stem(word: str, expected: str) -> None:
    assert stem(word) == expected


def test_tokenize_drops_stopwords_and_punctuation() -> None:
    assert tokenize("Where is MY order?!") == ["order"]
