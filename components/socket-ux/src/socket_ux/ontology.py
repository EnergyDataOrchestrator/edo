"""Ontology term search over the internal graph database — the CCA term
recommendation backend (UPL-004 Stage 3).

The socket searches the labels of the terms the system actually knows:
subjects in the Fuseki ``/projects`` dataset carrying ``rdfs:label``,
``skos:prefLabel``/``skos:altLabel`` or ``dcterms:title``. The candidate pool
grows with the semantic grounding of the system — instrument projects bring
their SMS measured quantities, Stage 2 (regimo publishes column metadata)
brings data-file columns, and the regimo-ontology publication brings the
curated vocabulary. Recommendations are therefore honest: a query with no
match returns an empty candidate list, never an invented term.

Ranking is lexical, deterministic and explainable: exact label > label
starting with the query > word-boundary token match > substring; more matched
query tokens rank higher. ``confidence_score`` is the normalised rank
(1.0 = exact) — the presentation layer of the CCA bounded context, not a
statistical claim.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from .config import Settings

LABEL_PROPS = (
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2004/02/skos/core#altLabel",
    "http://purl.org/dc/terms/title",
)

DESCRIPTION_PROPS = (
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2004/02/skos/core#definition",
    "http://purl.org/dc/terms/description",
)

_SEARCH_LIMIT = 200  # SPARQL pre-filter cap before client-side ranking


class OntologyError(RuntimeError):
    """Raised when the term search cannot be executed."""


def _sparql_string(value: str) -> str:
    """Escape a value for a SPARQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _contains_filter(var: str, needle: str) -> str:
    return f'FILTER(CONTAINS(LCASE(STR({var})), LCASE("{_sparql_string(needle)}")))'


def _sparql_list(iris) -> str:
    return ", ".join(f"<{p}>" for p in iris)


def search_query(needle: str) -> str:
    """The SPARQL SELECT behind the term search (exposed for tests/tools)."""
    labels = _sparql_list(LABEL_PROPS)
    descriptions = _sparql_list(DESCRIPTION_PROPS)
    return f"""
    PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos:    <http://www.w3.org/2004/02/skos/core#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    SELECT DISTINCT ?term ?label ?description ?type WHERE {{
      ?term ?labelProp ?label .
      FILTER(?labelProp IN ({labels}))
      {_contains_filter('?label', needle)}
      OPTIONAL {{ ?term rdf:type ?type }}
      OPTIONAL {{ ?term ?descriptionProp ?description .
                 FILTER(?descriptionProp IN ({descriptions})) }}
    }} LIMIT {_SEARCH_LIMIT}
    """


def _term(binding: dict[str, Any], var: str) -> str:
    node = binding.get(var)
    return str(node.get("value") or "") if node else ""


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens of a column name or query."""
    return [t for t in re.split(r"[^0-9a-z]+", text.lower()) if t]


def score_label(label: str, tokens: list[str]) -> int | None:
    """Deterministic lexical score of a label against query tokens.

    Higher is better; ``None`` when the label does not match at all.
    exact=300 · every token at a word boundary=240 · label starting with a
    token=200 · any token at a word boundary=120 (+5 per extra matched
    token) · substring=60.
    """
    lowered = label.lower()
    if lowered == " ".join(tokens):
        return 300
    boundary = re.split(r"[^0-9a-z]+", lowered)
    matched = [t for t in tokens if t in boundary]
    if matched and len(matched) == len(tokens) and tokens:
        return 240
    if tokens and any(lowered.startswith(t) for t in tokens):
        return 200
    if matched:
        return 120 + 5 * (len(matched) - 1)
    if all(t in lowered for t in tokens):
        return 60
    return None


def search_terms(
    settings: Settings, client: httpx.Client, query: str, limit: int = 20,
) -> list[dict[str, Any]]:
    """Ranked ontology-term candidates for a free-text query.

    Returns ``[{uri, label, description, types, confidence_score}]`` — empty
    when nothing matches (never fabricated terms).
    """
    from .fuseki import FusekiError, _run_select  # local import avoids a cycle

    needle = query.strip()
    if not needle:
        return []
    tokens = tokenize(needle)
    try:
        bindings = _run_select(settings, search_query(needle), client)
    except FusekiError as exc:
        raise OntologyError(str(exc)) from exc

    candidates: dict[str, dict[str, Any]] = {}
    for row in bindings:
        uri = _term(row, "term")
        label = _term(row, "label")
        if not uri or not label:
            continue
        score = score_label(label, tokens)
        if score is None:
            # the SPARQL pre-filter is a substring check on some label — a
            # different label of a multi-labelled term may score 0; keep the
            # term only when any of its labels matches lexically
            continue
        entry = candidates.setdefault(uri, {
            "uri": uri, "label": label, "description": "", "types": [], "score": 0,
        })
        entry["score"] = max(entry["score"], score)
        entry["label"] = label if score >= entry["score"] else entry["label"]
        description = _term(row, "description")
        if description and not entry["description"]:
            entry["description"] = description
        rdf_type = _term(row, "type")
        if rdf_type and rdf_type not in entry["types"]:
            entry["types"].append(rdf_type)

    ranked = sorted(candidates.values(), key=lambda c: (-c["score"], c["label"]))
    results = [
        {
            "uri": c["uri"],
            "label": c["label"],
            "description": c["description"],
            "types": c["types"],
            "confidence_score": round(min(c["score"] / 300.0, 1.0), 2),
        }
        for c in ranked[: max(1, limit)]
    ]
    return results


def recommend_for_columns(
    settings: Settings, client: httpx.Client, columns: list[dict[str, Any]], limit: int = 5,
) -> list[dict[str, Any]]:
    """Term candidates per CSV column (the CCA batch endpoint).

    Strategies in deterministic order, results merged and deduplicated by
    IRI (best score wins): the full column name, then each token of the name,
    then — when the name alone found nothing — the first non-empty sample
    value. Every strategy runs against the same graph-backed search.
    """
    recommendations: list[dict[str, Any]] = []
    for column in columns:
        name = str(column.get("name") or "").strip()
        if not name:
            continue
        strategies = [name, *tokenize(name)]
        candidates: dict[str, dict[str, Any]] = {}
        for strategy in strategies:
            found = search_terms(settings, client, strategy, limit)
            for term in found:
                existing = candidates.get(term["uri"])
                if existing is None or term["confidence_score"] > existing["confidence_score"]:
                    candidates[term["uri"]] = term
        if not candidates:
            sample = next(
                (str(v).strip() for v in (column.get("sample_values") or []) if str(v).strip()),
                "",
            )
            if sample:
                for term in search_terms(settings, client, sample, limit):
                    candidates[term["uri"]] = term
        ranked = sorted(
            candidates.values(),
            key=lambda c: (-c["confidence_score"], c["label"]),
        )[: max(1, limit)]
        recommendations.append({"name": name, "candidates": ranked})
    return recommendations
