"""
Document discovery handler for natural language queries.
Enables users to ask about documents using conversational language.
"""

import re
from enum import Enum
from typing import Dict, Optional, Tuple


class DocumentQueryType(str, Enum):
    """Types of document-related queries users might ask."""

    LIST_ALL = "list_all"
    LIST_BY_TYPE = "list_by_type"
    LIST_BY_PRODUCT = "list_by_product"
    SEARCH_DOCUMENTS = "search_documents"
    GET_STATS = "get_stats"
    FIND_RECENT = "find_recent"
    COUNT_DOCUMENTS = "count_documents"


class DocumentQueryHandler:
    """Handles natural language queries about documents in the knowledge base."""

    def __init__(self):
        # Patterns for different types of document queries
        self.query_patterns = {
            DocumentQueryType.LIST_ALL: [
                r"(?:list|show|display)\s+(?:all\s+)?documents?",
                r"what\s+documents?\s+(?:do\s+you\s+have|are\s+available)",
                r"show\s+me\s+(?:the\s+)?(?:available\s+)?documents?",
                r"what\s+(?:files?|pdfs?)\s+are\s+in\s+(?:the\s+)?(?:knowledge\s+)?(?:base|database)",
                r"browse\s+(?:the\s+)?(?:knowledge\s+)?(?:base|database)",
            ],
            DocumentQueryType.LIST_BY_TYPE: [
                r"(?:list|show|find)\s+(?:all\s+)?(\w+)\s+(?:type\s+)?documents?",
                r"what\s+(\w+)\s+documents?\s+(?:do\s+you\s+have|are\s+available)",
                r"show\s+me\s+(?:all\s+)?(?:the\s+)?(\w+)\s+(?:files?|pdfs?|documents?)",
            ],
            DocumentQueryType.LIST_BY_PRODUCT: [
                r"(?:list|show|find)\s+documents?\s+(?:for|about|on)\s+(.+?)(?:\s+product|\s*$)",
                r"what\s+documents?\s+(?:do\s+you\s+have\s+)?(?:for|about|on)\s+(.+?)(?:\s+product|\s*$)",
                r"show\s+me\s+(?:all\s+)?(?:documents?\s+)?(?:for|about|on)\s+(.+?)(?:\s+product|\s*$)",
            ],
            DocumentQueryType.SEARCH_DOCUMENTS: [
                r"(?:find|search\s+for|look\s+for)\s+documents?\s+(?:with|containing|about)\s+(.+)",
                r"(?:find|search\s+for|look\s+for)\s+(?:files?|pdfs?)\s+(?:with|containing|about)\s+(.+)",
                r"documents?\s+(?:with|containing|about)\s+(.+)",
                r"(?:any\s+)?documents?\s+(?:on|about)\s+(.+)",
            ],
            DocumentQueryType.GET_STATS: [
                r"(?:how\s+many|count)\s+documents?",
                r"(?:knowledge\s+base|database)\s+(?:statistics|stats|summary)",
                r"what\s+(?:types?\s+of\s+)?documents?\s+(?:do\s+you\s+have|are\s+available)",
                r"(?:give\s+me\s+)?(?:an?\s+)?(?:overview|summary)\s+of\s+(?:the\s+)?documents?",
            ],
            DocumentQueryType.FIND_RECENT: [
                r"(?:latest|most\s+recent|newest)\s+documents?",
                r"recently\s+(?:added|uploaded|processed)\s+documents?",
                r"what\s+(?:new\s+)?documents?\s+(?:have\s+been\s+)?(?:added|uploaded)\s+recently",
            ],
            DocumentQueryType.COUNT_DOCUMENTS: [
                r"how\s+many\s+documents?\s+(?:do\s+you\s+have|are\s+there)",
                r"total\s+(?:number\s+of\s+)?documents?",
                r"document\s+count",
            ],
        }

        # Compile patterns for efficiency
        self.compiled_patterns = {}
        for query_type, patterns in self.query_patterns.items():
            self.compiled_patterns[query_type] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def analyze_query(self, query: str) -> Tuple[Optional[DocumentQueryType], Dict[str, str]]:
        """
        Analyze a user query to determine if it's asking about documents.

        Returns:
            Tuple of (query_type, extracted_params) or (None, {}) if not a document query
        """
        query = query.strip()

        for query_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(query)
                if match:
                    # Extract parameters based on query type
                    params = self._extract_parameters(query_type, match, query)
                    return query_type, params

        return None, {}

    def _extract_parameters(self, query_type: DocumentQueryType, match: re.Match, full_query: str) -> Dict[str, str]:
        """Extract parameters from the matched query."""
        params = {}

        if query_type == DocumentQueryType.LIST_BY_TYPE:
            if match.groups():
                params["document_type"] = match.group(1).strip()

        elif query_type == DocumentQueryType.LIST_BY_PRODUCT:
            if match.groups():
                product = match.group(1).strip()
                # Clean up common trailing words
                product = re.sub(r"\s+(documentation|docs?|manual|guide)s?$", "", product, flags=re.IGNORECASE)
                params["product_name"] = product

        elif query_type == DocumentQueryType.SEARCH_DOCUMENTS:
            if match.groups():
                params["search_term"] = match.group(1).strip()

        # Check for additional modifiers
        query_lower = full_query.lower()

        # Privacy level
        if "private" in query_lower:
            params["privacy_level"] = "private"
        elif "public" in query_lower:
            params["privacy_level"] = "public"

        # Limit hints
        if "first" in query_lower or "top" in query_lower:
            # Extract number if present
            number_match = re.search(r"(?:first|top)\s+(\d+)", query_lower)
            if number_match:
                params["limit"] = min(int(number_match.group(1)), 20)
            else:
                params["limit"] = 10

        # Recent/latest
        if any(word in query_lower for word in ["recent", "latest", "newest", "new"]):
            params["sort_by"] = "created_at"
            params["sort_order"] = "desc"

        return params

    def generate_response_prompt(self, query_type: DocumentQueryType, params: Dict[str, str], results: Dict) -> str:
        """Generate a natural language prompt for the AI to respond with document information."""

        if query_type == DocumentQueryType.GET_STATS:
            stats = results
            return f"""Please provide a helpful summary of the knowledge base statistics:

Total Documents: {stats['total_documents']}
Total Chunks: {stats['total_chunks']}
Average Chunks per Document: {stats['avg_chunks_per_document']}

Document Types: {', '.join([f'{t} ({c})' for t, c in stats['document_types'].items()])}
Products: {', '.join([f'{p} ({c})' for p, c in stats['product_breakdown'].items()])}
Privacy Levels: {', '.join([f'{p} ({c})' for p, c in stats['privacy_breakdown'].items()])}

Last Processed: {stats['last_processed'] or 'No recent processing'}

Format this information in a conversational, helpful way for the user."""

        elif query_type in [
            DocumentQueryType.LIST_ALL,
            DocumentQueryType.LIST_BY_TYPE,
            DocumentQueryType.LIST_BY_PRODUCT,
            DocumentQueryType.SEARCH_DOCUMENTS,
        ]:
            docs = results["documents"]
            total = results["total_count"]

            if not docs:
                filter_desc = ""
                if params.get("document_type"):
                    filter_desc = f" of type '{params['document_type']}'"
                elif params.get("product_name"):
                    filter_desc = f" for product '{params['product_name']}'"
                elif params.get("search_term"):
                    filter_desc = f" matching '{params['search_term']}'"

                return f"No documents found{filter_desc}. You might want to check the available document types or try a different search term."

            doc_list = []
            for doc in docs:
                doc_info = f"• {doc['file_name']}"
                if doc["document_type"]:
                    doc_info += f" ({doc['document_type']})"
                if doc["product_name"]:
                    doc_info += f" - {doc['product_name']}"
                if doc["product_version"]:
                    doc_info += f" v{doc['product_version']}"
                doc_info += f" - {doc['chunk_count']} chunks"
                doc_list.append(doc_info)

            doc_summary = "\n".join(doc_list[:10])  # Limit to first 10 for readability

            more_info = ""
            if len(docs) > 10:
                more_info = f"\n\nShowing first 10 of {len(docs)} documents returned."
            if total > len(docs):
                more_info += f" Total matching documents: {total}."

            return f"""Here are the documents I found:

{doc_summary}{more_info}

You can ask me to search within these documents, get more details about a specific document, or filter by different criteria."""

        elif query_type == DocumentQueryType.FIND_RECENT:
            docs = results["documents"]
            if not docs:
                return "No recently processed documents found."

            recent_list = []
            for doc in docs[:5]:  # Show top 5 recent
                recent_list.append(f"• {doc['file_name']} - processed {doc['processed_at']}")

            return f"""Here are the most recently processed documents:

{chr(10).join(recent_list)}

These documents are ready for search and can provide answers to your questions."""

        elif query_type == DocumentQueryType.COUNT_DOCUMENTS:
            total = results["total_count"]
            return f"I have {total} documents in my knowledge base. Would you like to see a breakdown by type or product, or search for specific documents?"

        return (
            "I found some document information, but I'm not sure how to present it. Could you rephrase your question?"
        )


# Global handler instance
document_query_handler = DocumentQueryHandler()
