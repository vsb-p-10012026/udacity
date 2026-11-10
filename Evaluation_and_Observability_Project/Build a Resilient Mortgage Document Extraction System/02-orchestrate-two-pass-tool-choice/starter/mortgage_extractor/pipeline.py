"""Two-pass extraction pipeline: classify, then extract.

The classification pass uses ``tool_choice={"type":"tool","name":...}`` — the
model is forced to call the classifier and cannot return free text. The
extraction pass uses ``tool_choice={"type":"any"}`` against a small set of
doc-type-specific tools (a primary extractor plus a ``flag_for_review`` escape
hatch). ``"any"`` rather than ``"auto"`` because ``"auto"`` would permit a
conversational text fallback; ``"any"`` guarantees a ``tool_use`` block.

This pattern mirrors the Architect's Playbook "broad-then-pinpoint" exploration
recipe: classify the document first, then drill into the doc-type-specific
extractor with a fallback for unrecoverable cases.
"""
from __future__ import annotations

import logging

from anthropic.types import Message, ToolUseBlock

from mortgage_extractor import prompts
from mortgage_extractor.client import RecordingClient
from mortgage_extractor.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from mortgage_extractor.errors import (
    ExtractionError,
    FlaggedForReviewError,
    UnsupportedDocumentTypeError,
)
from mortgage_extractor.models import (
    Classification,
    DocumentType,
    MortgageExtraction,
)
from mortgage_extractor.tools import (
    ToolDefinition,
    classify_document,
    doc_type_extractor,
    flag_for_review,
)

log = logging.getLogger(__name__)


class Pipeline:
    """Two-pass classifier + extractor over the Anthropic Messages API."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        client: RecordingClient | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.model = model
        self.client = client or RecordingClient()
        self.max_tokens = max_tokens

    def run(self, document_text: str) -> MortgageExtraction:
        """Classify, then extract. Short-circuit on DocumentType.OTHER."""
        # TODO: Run the two-pass flow:
        #   1. Call self.classify_document(document_text). Save the result.
        #   2. If the classified document_type is DocumentType.OTHER, raise
        #      UnsupportedDocumentTypeError with the classification's reason.
        #      (The error class is already imported.)
        #   3. Otherwise return self.extract(document_text, classification.document_type).
        classification = self.classify_document(document_text)
        if classification.document_type == DocumentType.OTHER:
            raise UnsupportedDocumentTypeError(classification.reason)
        return self.extract(document_text, classification.document_type)

    def classify_document(self, document_text: str) -> Classification:
        """Pass 1: forced classifier call.

        Force the model to call the classifier tool exactly once via
        ``tool_choice={"type": "tool", "name": <classifier name>}``. This pass
        must produce a routing decision, not free text.
        """
        # TODO: Implement pass 1.
        #   - Get the classifier tool definition by calling classify_document()
        #     (the function imported from mortgage_extractor.tools).
        #   - Call self.client.call(...) with these kwargs:
        #       model=self.model,
        #       max_tokens=self.max_tokens,
        #       system=prompts.classifier_system_prompt(),
        #       tools=[<the classifier tool definition>],
        #       tool_choice={"type": "tool", "name": <the classifier's name>},
        #       messages=[{"role": "user", "content": document_text}],
        #   - Pass the response to _single_tool_use_block(..., expected_name=<classifier name>).
        #   - Return Classification.model_validate(block.input).
        classifier_tool = classify_document()
        response = self.client.call(
            model=self.model,
            max_tokens=self.max_tokens,
            system=prompts.classifier_system_prompt(),
            tools=[classifier_tool],
            tool_choice={"type": "tool", "name": classifier_tool["name"]},
            messages=[{"role": "user", "content": document_text}],
        )
        block = _single_tool_use_block(response, expected_name=classifier_tool["name"])
        return Classification.model_validate(block.input)

    def extract(
        self,
        document_text: str,
        doc_type: DocumentType,
    ) -> MortgageExtraction:
        """Pass 2: tool_choice="any" extraction.

        Register the doc-type-specific extractor alongside ``flag_for_review``
        and let the model choose. ``"any"`` is what makes that choice
        meaningful — with a single tool registered, the API would behave the
        same as forced.
        """
        # TODO: Implement pass 2.
        #   - Defensive guard: if doc_type is DocumentType.OTHER, raise
        #     UnsupportedDocumentTypeError immediately with a message that
        #     says extract() should not be called for OTHER (the classifier
        #     short-circuits earlier). This guard makes extract() safe for
        #     callers who bypass run().
        #   - Build tools = [doc_type_extractor(doc_type), flag_for_review()].
        #   - Call self.client.call(...) with:
        #       model=self.model,
        #       max_tokens=self.max_tokens,
        #       system=prompts.extractor_system_prompt(doc_type),
        #       tools=tools,
        #       tool_choice={"type": "any"},
        #       messages=[{"role": "user", "content": document_text}],
        #   - Pass the response to _single_tool_use_block(response).
        #   - If the block.name is "flag_for_review", raise FlaggedForReviewError
        #     with the reason from block.input.
        #   - If the block.name is the doc-type extractor's name, return
        #     MortgageExtraction.model_validate(block.input).
        #   - Otherwise raise ExtractionError because an unexpected tool was called.
        if doc_type == DocumentType.OTHER:
            raise UnsupportedDocumentTypeError(
                "extract() should not be called for DocumentType.OTHER."
            )

        extractor = doc_type_extractor(doc_type)
        tools = [extractor, flag_for_review()]

        response = self.client.call(
            model=self.model,
            max_tokens=self.max_tokens,
            system=prompts.extractor_system_prompt(doc_type),
            tools=tools,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": document_text}],
        )

        block = _single_tool_use_block(response)

        if block.name == "flag_for_review":
            reason = block.input.get("reason", "Document flagged for review.") if isinstance(block.input, dict) else "Document flagged for review."
            raise FlaggedForReviewError(reason)

        if block.name == extractor["name"]:
            return MortgageExtraction.model_validate(block.input)

        raise ExtractionError(f"Unexpected tool called: {block.name}")


def _single_tool_use_block(
    response: Message,
    *,
    expected_name: str | None = None,
) -> ToolUseBlock:
    """Pull the one ToolUseBlock out of an Anthropic Message response.

    Structured output lives in the ``tool_use`` block, not in the assistant
    text. Walk ``response.content`` looking for ``ToolUseBlock`` entries; if
    ``expected_name`` is set, narrow to matching blocks.
    """
    # TODO: Implement the tool-use extractor.
    #   - Filter response.content for instances of ToolUseBlock.
    #   - If there are none, raise ExtractionError with a message that lists
    #     the actual content-block types received (e.g. ["TextBlock"]).
    #   - If expected_name is None, return the first tool-use block.
    #   - Otherwise return the first block whose .name == expected_name. If
    #     none match, raise ExtractionError naming the block names received.
    tool_blocks = [block for block in response.content if isinstance(block, ToolUseBlock)]

    if not tool_blocks:
        received_types = [type(block).__name__ for block in response.content]
        raise ExtractionError(
            f"Expected a ToolUseBlock, but received content block types: {received_types}"
        )

    if expected_name is None:
        return tool_blocks[0]

    matching_blocks = [block for block in tool_blocks if block.name == expected_name]
    if not matching_blocks:
        received_names = [block.name for block in tool_blocks]
        raise ExtractionError(
            f"Expected tool '{expected_name}', but received tool block names: {received_names}"
        )

    return matching_blocks[0]
