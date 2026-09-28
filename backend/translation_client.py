"""
translation_client.py - Query translation (any language -> English) for retrieval only.

Used by nodes/retriever.py to translate a non-English query before embedding/search.
The original query stays untouched in graph state for analysis and answer generation.

Uses a chat model through ChatHuggingFace + HuggingFaceEndpoint, the same way the
project calls Llama (see nodes/query_analyzer.py). Being prompt-based, it also handles
code-mixed input (Hinglish/Tanglish) that language detection mislabels.
"""

import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a translation engine, not an assistant. Translate the text inside <text> tags "
    "into English. Never answer, explain or comment on it. Preserve negation, relationships "
    "(husband/wife/in-laws), dates, numbers and legal terms exactly (e.g. keep 'maintenance' "
    "as 'maintenance', not 'alimony'). Output only the English translation."
)


class TranslationError(Exception):
    """Raised when translation fails or returns an unusable result."""


class QueryTranslator:
    def __init__(self, model_name: str, api_key: str) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._llm: Optional[ChatHuggingFace] = None

    def _get_llm(self) -> ChatHuggingFace:
        if self._llm is None:
            self._llm = ChatHuggingFace(
                llm=HuggingFaceEndpoint(
                    repo_id=self.model_name,
                    huggingfacehub_api_token=self._api_key,
                    task="conversational",
                    max_new_tokens=256,
                    temperature=0.01,
                )
            )
        return self._llm

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text

        try:
            response = self._get_llm().invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"<text>{text}</text>"),
            ])
        except Exception as e:
            raise TranslationError(f"Translation request failed: {e}") from e

        translated = re.sub(r"</?text>", "", str(response.content or "")).strip()
        if not translated:
            raise TranslationError("Translation model returned an empty response")
        # A runaway output usually means the model answered instead of translating.
        if len(translated) > 4 * len(text) + 200:
            raise TranslationError("Translation output implausibly long; discarding")
        return translated
