"""Task-Specific Model Router with Automatic Confidence-Based Escalation.

Follows v2 Reliability Requirement 1:
Weak local LLM on Hindi/Hinglish legal text ->
(a) ModelRouter: per-task model config (extraction, judging, summary, translation)
    with optional escalation to a larger local model on low confidence.
"""

from enum import Enum
from typing import Type, TypeVar, Optional, Tuple, Callable, Any, Dict
import logging
from pydantic import BaseModel

from app.config import get_settings
from app.llm.client import (
    LLMClient,
    OpenAICompatClient,
    get_llm_client,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class TaskType(str, Enum):
    EXTRACTION = "extraction"
    JUDGING = "judging"
    SUMMARY = "summary"
    TRANSLATION = "translation"


class ModelRouter:
    """Routes LLM inference tasks to dedicated local models with escalation fallback."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        base_url: Optional[str] = None,
    ):
        self._default_client = llm_client
        self.settings = get_settings()
        self.base_url = base_url or self.settings.LLM_BASE_URL
        self.escalation_threshold = self.settings.MODEL_ESCALATION_CONFIDENCE_THRESHOLD

        # Model mapping per task
        self.task_models: Dict[TaskType, str] = {
            TaskType.EXTRACTION: self.settings.TASK_MODEL_EXTRACTION,
            TaskType.JUDGING: self.settings.TASK_MODEL_JUDGE,
            TaskType.SUMMARY: self.settings.TASK_MODEL_SUMMARY,
            TaskType.TRANSLATION: self.settings.TASK_MODEL_TRANSLATE,
        }
        self.escalation_model = self.settings.TASK_MODEL_ESCALATION

    def get_model_for_task(self, task: TaskType) -> str:
        """Resolve the primary model identifier assigned to a specific task."""
        return self.task_models.get(task, self.settings.LLM_MODEL)

    def get_client_for_task(self, task: TaskType) -> LLMClient:
        """Instantiate or retrieve LLMClient for a specific task."""
        model_name = self.get_model_for_task(task)
        return self.get_client_for_model(model_name)

    def get_client_for_model(self, model_name: str) -> LLMClient:
        """Instantiate or retrieve LLMClient for a specific model."""
        if self._default_client is not None:
            # If a test client (e.g. FakeLLMClient) is injected, reuse it
            return self._default_client
        return OpenAICompatClient(base_url=self.base_url, model=model_name)

    def run_structured(
        self,
        task: TaskType,
        schema: Type[T],
        prompt: str,
        system: Optional[str] = None,
        confidence_extractor: Optional[Callable[[T], float]] = None,
    ) -> Tuple[T, bool, str]:
        """Execute structured JSON generation for a task, escalating if confidence is low.
        
        Returns:
            Tuple[T, bool, str]: (result_model, was_escalated, model_used)
        """
        primary_model = self.get_model_for_task(task)
        client = self.get_client_for_model(primary_model)

        # Primary pass
        res, review_needed = client.generate_structured(prompt=prompt, schema=schema, system=system)

        # Determine confidence
        confidence = 1.0
        if confidence_extractor is not None:
            try:
                confidence = confidence_extractor(res)
            except Exception:
                confidence = 0.5 if review_needed else 1.0
        elif hasattr(res, "confidence"):
            confidence = getattr(res, "confidence", 1.0)
        elif review_needed:
            confidence = 0.5

        # Check if escalation is warranted
        if (confidence < self.escalation_threshold or review_needed) and primary_model != self.escalation_model:
            logger.info(
                f"ModelRouter: Confidence {confidence:.2f} < threshold {self.escalation_threshold}. "
                f"Escalating task '{task.value}' from '{primary_model}' to '{self.escalation_model}'."
            )
            escalation_client = self.get_client_for_model(self.escalation_model)
            try:
                escalated_res, escalated_review = escalation_client.generate_structured(
                    prompt=prompt, schema=schema, system=system
                )
                escalated_conf = confidence
                if confidence_extractor is not None:
                    try:
                        escalated_conf = confidence_extractor(escalated_res)
                    except Exception:
                        escalated_conf = 0.5 if escalated_review else 1.0
                elif hasattr(escalated_res, "confidence"):
                    escalated_conf = getattr(escalated_res, "confidence", 1.0)

                # If escalated result improved, use it
                if escalated_conf >= confidence:
                    return escalated_res, True, self.escalation_model
            except Exception as e:
                logger.warning(f"ModelRouter: Escalation to '{self.escalation_model}' failed: {e}. Keeping primary.")

        return res, False, primary_model

