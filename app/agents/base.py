"""Base Agent Class for all LexAgent intelligence agents.

Follows Hard Rule 1: Every agent = one class with: typed Pydantic input, typed Pydantic output,
run() method, no hidden global state. Agents talk to each other ONLY through Pydantic schemas.
Follows Hard Rule 3: Every agent output carries confidence (0-1) and needs_human_review (bool).
Follows Hard Rule 5: Every agent run writes an append-only audit log row.
Follows Hard Rule 10: Injects mandatory legal decision-support disclaimer.
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional
from app.config import get_settings
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.security.audit import record_audit_event
from app.llm.client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

TInput = TypeVar("TInput", bound=BaseAgentInput)
TOutput = TypeVar("TOutput", bound=BaseAgentOutput)


class BaseAgent(ABC, Generic[TInput, TOutput]):
    """Abstract agent enforcing typed I/O, audit logging, and safety constraints."""

    agent_name: str = "BaseAgent"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self.settings = get_settings()

    @abstractmethod
    def _execute(self, input_data: TInput) -> TOutput:
        """Internal execution method implemented by subclasses."""
        pass

    def run(self, input_data: TInput) -> TOutput:
        """Standard execution wrapper with audit logging and threshold safety guards."""
        actor_name = f"agent:{self.agent_name}"
        req_id = getattr(input_data, "request_id", None)

        try:
            output = self._execute(input_data)

            # Extract engine execution status
            engine_used = getattr(output, "engine", "rules")
            llm_called = bool(getattr(output, "llm_called", False))
            fallback_taken = bool(getattr(output, "fallback_taken", False))

            # Task 1: Required structured log line
            logger.info(
                f"AGENT_EXECUTION: agent={self.agent_name} engine={engine_used} "
                f"llm_called={llm_called} fallback_taken={fallback_taken}"
            )

            # Enforce confidence threshold guard
            if output.confidence < self.settings.CONFIDENCE_THRESHOLD:
                output.needs_human_review = True
                if not output.audit_notes:
                    output.audit_notes = (
                        f"Confidence ({output.confidence:.2f}) below threshold "
                        f"({self.settings.CONFIDENCE_THRESHOLD:.2f}). Flagged for advocate review."
                    )

            # Ensure disclaimer is always populated
            if not output.disclaimer:
                output.disclaimer = self.settings.DISCLAIMER_TEXT

            # Hard Rule 5: Write append-only audit log row
            record_audit_event(
                event_type="AGENT_RUN",
                actor=actor_name,
                resource_id=req_id,
                input_payload=input_data.model_dump(),
                output_payload=output.model_dump(),
                confidence=output.confidence,
                needs_human_review=output.needs_human_review,
                status="SUCCESS",
            )
            return output

        except Exception as e:
            logger.info(
                f"AGENT_EXECUTION: agent={self.agent_name} engine=error "
                f"llm_called=False fallback_taken=True"
            )
            # Audit log failure
            record_audit_event(
                event_type="AGENT_RUN",
                actor=actor_name,
                resource_id=req_id,
                input_payload=input_data.model_dump(),
                output_payload={"error": str(e)},
                confidence=0.0,
                needs_human_review=True,
                status="ERROR",
            )
            raise

