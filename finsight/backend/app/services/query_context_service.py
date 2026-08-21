"""Query Context and Deterministic Follow-Up Resolution Service (Sprint 8.2)."""

import logging
import re
from typing import Sequence

from app.models.conversation import ConversationMessage

logger = logging.getLogger("finsight.services.query_context")

FOLLOWUP_PATTERNS = [
    r"^(what|how)\s+about\s+",
    r"^and\s+(what|how)\s+",
    r"^how\s+much\s+(did\s+it|was\s+it|changed?)",
    r"^(what|how)\s+was\s+(it|that)\b",
    r"^(why|when)\s+did\s+(it|that)\b",
    r"^(what|how)\s+about\s+(in\s+)?(\d{4}|q[1-4]|ytd)",
    r"^(compare|contrast)\s+(it|that|this)\b",
    r"^(what\s+is|what's)\s+the\s+difference\b",
    r"^(what|how)\s+about\s+the\s+previous\s+year",
    r"^(how\s+did\s+that\s+compare)",
    r"^\s*(\d{4}|q[1-4]|q[1-4]\s+\d{4})\??\s*$",
]


class QueryContextService:
    """
    Analyzes recent conversation history to resolve simple follow-up references
    into standalone retrieval queries without altering the user's original question for the generator.
    """

    @classmethod
    def is_followup_query(cls, query: str) -> bool:
        """Check if a user query is likely a contextual follow-up."""
        q = query.strip().lower()
        if len(q.split()) <= 3 and any(char.isdigit() for char in q):
            return True
        for pattern in FOLLOWUP_PATTERNS:
            if re.search(pattern, q):
                return True
        return False

    @classmethod
    def resolve_retrieval_query(
        cls,
        current_query: str,
        recent_messages: Sequence[ConversationMessage],
    ) -> str:
        """
        Construct a focused retrieval query combining relevant entity/metric context
        from recent conversation history if current_query is a follow-up.
        Never concatenates raw assistant text blindly; extracts concise context only.
        """
        if not recent_messages:
            return current_query.strip()

        if not cls.is_followup_query(current_query):
            return current_query.strip()

        # Find the last user message that established context
        last_user_query = ""
        for msg in reversed(recent_messages):
            if msg.role == "user" and msg.content.strip():
                last_user_query = msg.content.strip()
                break

        if not last_user_query or last_user_query == current_query.strip():
            return current_query.strip()

        # Extract keywords and entity cues from last user query
        cleaned_prev = re.sub(r"[?.,!]", "", last_user_query)
        cleaned_curr = re.sub(r"[?.,!]", "", current_query)

        # Detect year/period in current query (e.g. "2024", "Q3")
        curr_periods = re.findall(r"\b(20\d\d|19\d\d|q[1-4]|ytd)\b", cleaned_curr, flags=re.IGNORECASE)

        # Remove previous periods from previous query and inject new periods
        base_context = cleaned_prev
        for p in re.findall(r"\b(20\d\d|19\d\d|q[1-4]|ytd)\b", base_context, flags=re.IGNORECASE):
            base_context = re.sub(r"\b" + p + r"\b", "", base_context, flags=re.IGNORECASE)

        base_context = re.sub(r"\s+", " ", base_context).strip()

        if curr_periods:
            resolved = f"{base_context} {' '.join(curr_periods)}".strip()
            logger.info("Resolved follow-up query '%s' -> '%s'", current_query, resolved)
            return resolved

        # Generic follow-up (e.g., "How much did it change?")
        resolved = f"{base_context} {cleaned_curr}".strip()
        logger.info("Resolved follow-up query '%s' -> '%s'", current_query, resolved)
        return resolved
