"""pySHACL adapter for validating projected news graphs."""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate
from rdflib import Graph

from ..domain.models import ShaclValidationResult


class ShaclValidator:
    """Load ontology assets once and validate candidate projections with RDFS inference."""

    def __init__(self, ontology_root: Path) -> None:
        self._ontology_graph = Graph()
        self._ontology_graph.parse(ontology_root / "core.ttl", format="turtle")
        self._ontology_graph.parse(ontology_root / "news.ttl", format="turtle")

        self._shapes_graph = Graph()
        self._shapes_graph.parse(
            ontology_root / "shapes/news-shapes.ttl", format="turtle"
        )

    def validate(self, candidate_graph: Graph) -> ShaclValidationResult:
        """Return the SHACL conformance result for a projected candidate graph."""
        conforms, _report_graph, report_text = validate(
            candidate_graph,
            shacl_graph=self._shapes_graph,
            ont_graph=self._ontology_graph,
            inference="rdfs",
        )
        return ShaclValidationResult(
            conforms=bool(conforms),
            report_text=str(report_text),
        )
