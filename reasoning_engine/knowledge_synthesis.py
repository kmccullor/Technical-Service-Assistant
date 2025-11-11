"""
Knowledge Synthesis Pipeline

Advanced knowledge synthesis capabilities for cross-document reasoning,
pattern recognition, and multi-perspective analysis.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from config import get_model_num_ctx
logger = logging.getLogger(__name__)


@dataclass
class KnowledgeCluster:
    """Represents a cluster of related knowledge pieces."""

    theme: str
    confidence: float
    source_documents: List[str]
    key_concepts: List[str]
    supporting_evidence: List[str]
    contradictions: List[str]
    synthesis: str


@dataclass
class CrossReferencePattern:
    """Represents a pattern found across multiple documents."""

    pattern_type: str
    description: str
    occurrences: List[Dict[str, Any]]
    strength: float
    documents_involved: Set[str]


@dataclass
class SynthesisResult:
    """Result of knowledge synthesis process."""

    main_synthesis: str
    knowledge_clusters: List[KnowledgeCluster]
    cross_patterns: List[CrossReferencePattern]
    conflicting_viewpoints: List[Dict[str, Any]]
    confidence_score: float
    synthesis_approach: str
    sources_analyzed: List[str]


class KnowledgeSynthesizer:
    """
    Advanced knowledge synthesis engine for cross-document reasoning.

    Capabilities:
    - Semantic clustering of related information
    - Pattern recognition across sources
    - Contradiction detection and resolution
    - Multi-perspective analysis
    - Evidence consolidation
    """

    def __init__(self, search_client, llm_client, settings):
        """Initialize knowledge synthesizer with required clients."""
        self.search_client = search_client
        self.llm_client = llm_client
        self.settings = settings

        # Synthesis configuration
        self.min_cluster_size = 2
        self.max_clusters = 10
        self.similarity_threshold = 0.7
        self.contradiction_threshold = 0.3

        logger.info("Knowledge synthesizer initialized")

    async def synthesize_knowledge(
        self, query: str, source_documents: List[Dict[str, Any]], synthesis_depth: str = "standard"
    ) -> SynthesisResult:
        """
        Main knowledge synthesis pipeline.

        Args:
            query: The research question or query
            source_documents: List of document chunks with text and metadata
            synthesis_depth: Level of synthesis ('shallow', 'standard', 'deep')

        Returns:
            SynthesisResult with comprehensive knowledge analysis
        """
        logger.info(f"Starting knowledge synthesis for query: {query[:100]}...")

        if not source_documents:
            return SynthesisResult(
                main_synthesis="No source documents provided for synthesis",
                knowledge_clusters=[],
                cross_patterns=[],
                conflicting_viewpoints=[],
                confidence_score=0.0,
                synthesis_approach=synthesis_depth,
                sources_analyzed=[],
            )

        try:
            # Step 1: Semantic clustering of information
            clusters = await self._cluster_related_information(source_documents, query)

            # Step 2: Cross-document pattern recognition
            patterns = await self._identify_cross_patterns(source_documents, query)

            # Step 3: Contradiction detection
            conflicts = await self._detect_contradictions(source_documents, query)

            # Step 4: Multi-perspective analysis
            perspectives = await self._analyze_perspectives(source_documents, query)

            # Step 5: Final synthesis
            main_synthesis = await self._generate_synthesis(
                query, clusters, patterns, conflicts, perspectives, synthesis_depth
            )

            # Calculate overall confidence
            confidence = self._calculate_synthesis_confidence(clusters, patterns, conflicts)

            return SynthesisResult(
                main_synthesis=main_synthesis,
                knowledge_clusters=clusters,
                cross_patterns=patterns,
                conflicting_viewpoints=conflicts,
                confidence_score=confidence,
                synthesis_approach=synthesis_depth,
                sources_analyzed=[doc.get("source", "unknown") for doc in source_documents],
            )

        except Exception as e:
            logger.error(f"Knowledge synthesis failed: {e}")
            return SynthesisResult(
                main_synthesis=f"Synthesis failed: {str(e)}",
                knowledge_clusters=[],
                cross_patterns=[],
                conflicting_viewpoints=[],
                confidence_score=0.0,
                synthesis_approach=synthesis_depth,
                sources_analyzed=[],
            )

    async def _cluster_related_information(self, documents: List[Dict[str, Any]], query: str) -> List[KnowledgeCluster]:
        """Group related information into thematic clusters."""
        logger.info("Clustering related information...")

        # Extract key concepts from each document
        concept_extractions = []
        for doc in documents:
            concepts = await self._extract_key_concepts(doc.get("text", ""), query)
            concept_extractions.append({"document": doc, "concepts": concepts, "text": doc.get("text", "")})

        # Group documents by concept similarity
        clusters = []
        processed_docs = set()

        for i, doc_info in enumerate(concept_extractions):
            if i in processed_docs:
                continue

            # Start new cluster
            cluster_docs = [doc_info]
            cluster_concepts = set(doc_info["concepts"])
            processed_docs.add(i)

            # Find similar documents
            for j, other_doc in enumerate(concept_extractions[i + 1 :], i + 1):
                if j in processed_docs:
                    continue

                # Calculate concept overlap
                other_concepts = set(other_doc["concepts"])
                overlap = len(cluster_concepts.intersection(other_concepts))
                total = len(cluster_concepts.union(other_concepts))

                if total > 0 and overlap / total >= self.similarity_threshold:
                    cluster_docs.append(other_doc)
                    cluster_concepts.update(other_concepts)
                    processed_docs.add(j)

            if len(cluster_docs) >= self.min_cluster_size:
                # Generate cluster synthesis
                cluster_theme = await self._generate_cluster_theme(cluster_docs, query)
                cluster_synthesis = await self._synthesize_cluster(cluster_docs, cluster_theme, query)

                cluster = KnowledgeCluster(
                    theme=cluster_theme,
                    confidence=min(0.9, 0.5 + len(cluster_docs) * 0.1),
                    source_documents=[doc["document"].get("source", "unknown") for doc in cluster_docs],
                    key_concepts=list(cluster_concepts)[:10],  # Limit to top concepts
                    supporting_evidence=[doc["text"][:200] + "..." for doc in cluster_docs],
                    contradictions=[],  # Will be filled in contradiction detection
                    synthesis=cluster_synthesis,
                )
                clusters.append(cluster)

        return clusters[: self.max_clusters]

    async def _identify_cross_patterns(
        self, documents: List[Dict[str, Any]], query: str
    ) -> List[CrossReferencePattern]:
        """Identify patterns that appear across multiple documents."""
        logger.info("Identifying cross-document patterns...")

        patterns = []

        try:
            # Use LLM to identify recurring themes and patterns
            pattern_prompt = f"""
            Analyze these documents for recurring patterns, themes, or structures related to: {query}

            Documents:
            {json.dumps([doc.get('text', '')[:500] for doc in documents[:10]], indent=2)}

            Identify:
            1. Recurring methodological approaches
            2. Common themes or concepts
            3. Similar data patterns or findings
            4. Consistent terminology usage
            5. Structural similarities

            Return as JSON with pattern_type, description, strength (0-1), and document_indices.
            """

            response = await self._call_llm(pattern_prompt, temperature=0.3, query=query)

            try:
                pattern_data = json.loads(response)
                if isinstance(pattern_data, list):
                    for pattern_info in pattern_data:
                        pattern = CrossReferencePattern(
                            pattern_type=pattern_info.get("pattern_type", "unknown"),
                            description=pattern_info.get("description", ""),
                            occurrences=[],  # Simplified for now
                            strength=pattern_info.get("strength", 0.5),
                            documents_involved=set([str(i) for i in pattern_info.get("document_indices", [])]),
                        )
                        patterns.append(pattern)
            except json.JSONDecodeError:
                logger.warning("Failed to parse pattern identification response")

        except Exception as e:
            logger.error(f"Pattern identification failed: {e}")

        return patterns

    async def _detect_contradictions(self, documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Detect conflicting information across documents."""
        logger.info("Detecting contradictions...")

        contradictions = []

        try:
            # Compare documents pairwise for contradictions
            for i, doc1 in enumerate(documents):
                for j, doc2 in enumerate(documents[i + 1 :], i + 1):
                    contradiction = await self._compare_for_contradictions(
                        doc1.get("text", ""), doc2.get("text", ""), query
                    )

                    if contradiction:
                        contradictions.append(
                            {
                                "document_1": doc1.get("source", f"doc_{i}"),
                                "document_2": doc2.get("source", f"doc_{j}"),
                                "contradiction_type": contradiction.get("type", "factual"),
                                "description": contradiction.get("description", ""),
                                "severity": contradiction.get("severity", "medium"),
                                "evidence_1": doc1.get("text", "")[:200],
                                "evidence_2": doc2.get("text", "")[:200],
                            }
                        )

        except Exception as e:
            logger.error(f"Contradiction detection failed: {e}")

        return contradictions

    async def _analyze_perspectives(self, documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Analyze different perspectives present in the documents."""
        logger.info("Analyzing multiple perspectives...")

        perspectives = []

        try:
            perspective_prompt = f"""
            Analyze these documents for different perspectives, viewpoints, or approaches to: {query}

            Documents:
            {json.dumps([doc.get('text', '')[:400] for doc in documents[:8]], indent=2)}

            Identify distinct perspectives including:
            1. Methodological approaches
            2. Theoretical frameworks
            3. Cultural or regional viewpoints
            4. Temporal perspectives (historical vs modern)
            5. Disciplinary perspectives

            For each perspective, provide:
            - Name/label
            - Key characteristics
            - Supporting documents
            - Strength of evidence

            Return as JSON array.
            """

            response = await self._call_llm(perspective_prompt, temperature=0.4, query=query)

            try:
                perspectives = json.loads(response)
                if not isinstance(perspectives, list):
                    perspectives = []
            except json.JSONDecodeError:
                logger.warning("Failed to parse perspective analysis response")
                perspectives = []

        except Exception as e:
            logger.error(f"Perspective analysis failed: {e}")

        return perspectives

    async def _generate_synthesis(
        self,
        query: str,
        clusters: List[KnowledgeCluster],
        patterns: List[CrossReferencePattern],
        conflicts: List[Dict[str, Any]],
        perspectives: List[Dict[str, Any]],
        depth: str,
    ) -> str:
        """Generate final knowledge synthesis."""
        logger.info("Generating knowledge synthesis...")

        try:
            synthesis_prompt = f"""
            Create a comprehensive synthesis for the query: {query}

            Based on the analysis:

            Knowledge Clusters ({len(clusters)} found):
            {json.dumps([{'theme': c.theme, 'synthesis': c.synthesis} for c in clusters], indent=2)}

            Cross-Document Patterns ({len(patterns)} found):
            {json.dumps([{'type': p.pattern_type, 'description': p.description} for p in patterns], indent=2)}

            Conflicting Information ({len(conflicts)} found):
            {json.dumps([{'type': c.get('contradiction_type'), 'description': c.get('description')} for c in conflicts], indent=2)}

            Multiple Perspectives ({len(perspectives)} found):
            {json.dumps(perspectives, indent=2)}

            Synthesis Depth: {depth}

            Provide a {depth} synthesis that:
            1. Integrates findings from all clusters
            2. Acknowledges cross-document patterns
            3. Addresses contradictions appropriately
            4. Incorporates multiple perspectives
            5. Draws meaningful conclusions
            6. Identifies knowledge gaps or limitations

            {"Be thorough and detailed." if depth == "deep" else "Be concise but comprehensive." if depth == "standard" else "Provide a brief summary."}
            """

            return await self._call_llm(synthesis_prompt, temperature=0.6, query=query)

        except Exception as e:
            logger.error(f"Synthesis generation failed: {e}")
            return f"Failed to generate synthesis: {str(e)}"

    async def _extract_key_concepts(self, text: str, query: str) -> List[str]:
        """Extract key concepts from text relevant to the query."""
        try:
            concept_prompt = f"""
            Extract key concepts from this text that are relevant to: {query}

            Text: {text[:1000]}

            Return only a comma-separated list of key concepts (max 10).
            """

            response = await self._call_llm(concept_prompt, temperature=0.3, query=query)
            concepts = [c.strip() for c in response.split(",") if c.strip()]
            return concepts[:10]

        except Exception as e:
            logger.error(f"Concept extraction failed: {e}")
            return []

    async def _generate_cluster_theme(self, cluster_docs: List[Dict[str, Any]], query: str) -> str:
        """Generate a thematic label for a document cluster."""
        try:
            theme_prompt = f"""
            Generate a concise theme or topic name for these related documents in the context of: {query}

            Documents:
            {json.dumps([doc['text'][:300] for doc in cluster_docs], indent=2)}

            Return only the theme name (2-5 words).
            """

            return await self._call_llm(theme_prompt, temperature=0.3, query=query)

        except Exception as e:
            logger.error(f"Theme generation failed: {e}")
            return "Unknown Theme"

    async def _synthesize_cluster(self, cluster_docs: List[Dict[str, Any]], theme: str, query: str) -> str:
        """Generate synthesis for a single cluster."""
        try:
            cluster_prompt = f"""
            Synthesize information about '{theme}' from these documents in relation to: {query}

            Documents:
            {json.dumps([doc['text'][:400] for doc in cluster_docs], indent=2)}

            Provide a concise synthesis (2-3 sentences) that captures the main insights.
            """

            return await self._call_llm(cluster_prompt, temperature=0.5, query=query)

        except Exception as e:
            logger.error(f"Cluster synthesis failed: {e}")
            return f"Synthesis failed for theme: {theme}"

    async def _compare_for_contradictions(self, text1: str, text2: str, query: str) -> Optional[Dict[str, Any]]:
        """Compare two texts for contradictory information."""
        try:
            comparison_prompt = f"""
            Compare these two texts for contradictory information regarding: {query}

            Text 1: {text1[:500]}
            Text 2: {text2[:500]}

            If contradictions exist, return JSON with:
            {{"type": "factual/methodological/interpretive", "description": "brief description", "severity": "low/medium/high"}}

            If no contradictions, return: null
            """

            response = await self._call_llm(comparison_prompt, temperature=0.2, query=query)

            try:
                result = json.loads(response.strip())
                return result if result and isinstance(result, dict) else None
            except json.JSONDecodeError:
                return None

        except Exception as e:
            logger.error(f"Contradiction comparison failed: {e}")
            return None

    def _calculate_synthesis_confidence(
        self, clusters: List[KnowledgeCluster], patterns: List[CrossReferencePattern], conflicts: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence in the synthesis."""
        if not clusters:
            return 0.0

        # Base confidence from cluster quality
        cluster_confidence = sum(c.confidence for c in clusters) / len(clusters)

        # Boost from patterns
        pattern_boost = min(0.2, len(patterns) * 0.05)

        # Penalty from conflicts
        conflict_penalty = min(0.3, len(conflicts) * 0.1)

        confidence = cluster_confidence + pattern_boost - conflict_penalty
        return max(0.0, min(1.0, confidence))

    def _select_model_for_query(self, query: Optional[str]) -> str:
        """Heuristically select the best model for the supplied query."""
        default_model = getattr(self.settings, "reasoning_model", getattr(self.settings, "chat_model", "mistral:7b"))
        if not query:
            return default_model

        q = query.lower()
        coding_keywords = ["code", "debug", "function", "script", "program", "api"]
        vision_keywords = ["image", "diagram", "visual", "picture", "chart", "graph"]
        reasoning_keywords = ["reason", "analyze", "compare", "evaluate", "explain", "steps"]

        if any(keyword in q for keyword in coding_keywords):
            return getattr(self.settings, "coding_model", default_model)
        if any(keyword in q for keyword in vision_keywords):
            return getattr(self.settings, "vision_model", default_model)
        if any(keyword in q for keyword in reasoning_keywords) or len(q) > 300:
            return getattr(self.settings, "reasoning_model", default_model)
        return getattr(self.settings, "chat_model", default_model)

    async def _call_llm(self, prompt: str, temperature: float = 0.7, query: Optional[str] = None) -> str:
        """Make LLM call with error handling."""
        try:
            model_name = self._select_model_for_query(query)
            options = {"temperature": temperature}
            num_ctx = get_model_num_ctx(model_name)
            if num_ctx:
                options["num_ctx"] = num_ctx

            response = self.llm_client.chat(
                model=model_name, messages=[{"role": "user", "content": prompt}], options=options
            )
            return response["message"]["content"]

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"LLM generation failed: {str(e)}"
