"""Policy search. Deliberately naive keyword matching; week 4 replaces it with pgvector
hybrid search behind the same tool definition, and measures the recall difference."""

import re
from collections import Counter

from pydantic import BaseModel, Field

from supportdesk.tools.base import Tool, ToolContext, ToolInput

# fmt: off
STOPWORDS = frozenset({
    "a", "an", "and", "are", "be", "can", "do", "does", "for", "from", "how", "i", "if",
    "in", "is", "it", "my", "of", "on", "or", "the", "to", "was", "what", "when", "where",
    "which", "who", "why", "will", "with", "you", "your", "have", "so", "any", "get",
})
SUFFIXES = ("ing", "ed", "es", "s", "e")  # longest first
# fmt: on
# Go: var stopwords = map[string]bool{"a": true, ...}. frozenset = immutable set.
# `# fmt: off/on` stops the formatter from putting one word per line.


MIN_STEM = 4


def stem(word: str) -> str:
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= MIN_STEM:
            return word.removesuffix(suffix)
    return word


# Go:
#   func stem(w string) string {
#       for _, suf := range suffixes {
#           if strings.HasSuffix(w, suf) && len(w)-len(suf) >= minStem {
#               return strings.TrimSuffix(w, suf)
#           }
#       }
#       return w
#   }
# Crude on purpose: damaged/damage/damages -> "damag", refunded/refunds -> "refund".
# Good enough to be a baseline; week 4 replaces it with embeddings + full-text search.


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS]


# Go:
#   var wordRe = regexp.MustCompile(`[a-z0-9]+`)
#   func tokenize(text string) []string {
#       var out []string
#       for _, w := range wordRe.FindAllString(strings.ToLower(text), -1) {
#           if !stopwords[w] { out = append(out, stem(w)) }
#       }
#       return out
#   }
# The comprehension reads: [transform(x) for x in items if condition].


class SearchPoliciesInput(ToolInput):
    query: str = Field(
        min_length=2,
        max_length=500,
        description="What to look for, in plain words, e.g. 'return window for damaged items'.",
    )
    top_k: int = Field(default=3, ge=1, le=10, description="How many sections to return.")


class PolicyHit(BaseModel):
    citation: str
    doc_id: str
    doc_title: str
    section_id: str
    heading: str
    text: str
    score: int


class SearchPoliciesOutput(BaseModel):
    query: str
    results: list[PolicyHit]


def search_policies(ctx: ToolContext, args: SearchPoliciesInput) -> SearchPoliciesOutput:
    terms = set(tokenize(args.query))
    hits: list[PolicyHit] = []
    for doc in ctx.repo.list_policies():
        for section in doc.sections:
            heading_counts = Counter(tokenize(section.heading))
            text_counts = Counter(tokenize(section.text))
            score = sum(2 * heading_counts[t] + text_counts[t] for t in terms)
            if score > 0:
                hits.append(
                    PolicyHit(
                        citation=f"{doc.id} §{section.id}",
                        doc_id=doc.id,
                        doc_title=doc.title,
                        section_id=section.id,
                        heading=section.heading,
                        text=section.text,
                        score=score,
                    )
                )
    hits.sort(key=lambda h: (-h.score, h.citation))
    return SearchPoliciesOutput(query=args.query, results=hits[: args.top_k])


# Go:
#   func SearchPolicies(ctx ToolContext, in SearchPoliciesInput) (SearchPoliciesOutput, error) {
#       terms := toSet(tokenize(in.Query))
#       var hits []PolicyHit
#       for _, doc := range ctx.Repo.ListPolicies() {
#           for _, s := range doc.Sections {
#               score := 0
#               for t := range terms { score += 2*count(s.Heading, t) + count(s.Text, t) }
#               if score > 0 { hits = append(hits, PolicyHit{...}) }
#           }
#       }
#       sort.Slice(hits, func(i, j int) bool { ... score desc, citation asc ... })
#       return SearchPoliciesOutput{Query: in.Query, Results: hits[:min(in.TopK, len(hits))]}, nil
#   }
#
# Counter is a map[string]int that returns 0 for missing keys. sort with key=: Python
# sorts by a computed key instead of a less() func; a tuple key sorts by the first
# element, then the second (tie-break keeps results deterministic). hits[:k] never
# panics when k > len(hits) - slicing clamps.
# No match is NOT an error: an empty result list tells the model "no policy covers
# this", so it can say so instead of inventing one (trap #8 in the spec).

SEARCH_POLICIES = Tool(
    name="search_policies",
    description=(
        "Search ShopCo's customer-service policies (returns, refunds, shipping, damaged "
        "items, loyalty programme, account security). Returns the best-matching policy "
        "sections, each with a citation like 'POL-RETURNS §1' and the section text. "
        "Use it before stating any rule, deadline or amount, and cite the sections you "
        "rely on. An empty result means no policy covers the question: say so, do not "
        "make up a policy."
    ),
    input_model=SearchPoliciesInput,
    handler=search_policies,
)
