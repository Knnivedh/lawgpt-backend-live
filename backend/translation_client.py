"""
translation_client.py - Prepare a user's question for retrieval.

Used by nodes/retriever.py. Two things can be done to the question before it is
searched, both with one chat model called through LangChain: ChatHuggingFace +
HuggingFaceEndpoint (the same way the project calls Llama), or ChatOllama when
the provider is "ollama":

  translate()      any language -> faithful English
  prepare_search() faithful English AND a short neutral search query, in one call

The original query stays untouched in graph state for analysis and answer
generation. Being prompt-based, this also handles code-mixed input
(Hinglish/Tanglish) that language detection mislabels.
"""

import logging
import re
from typing import Dict, List, NamedTuple, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_ollama import ChatOllama

OLLAMA_PROVIDER = "ollama"

logger = logging.getLogger(__name__)

# The model once rendered Tamil "மாமியார்" (mother-in-law) as "aunt", which
# turns a matrimonial-home question into an unrelated one.
KINSHIP_RULE = (
    "Translate kinship terms exactly. Examples: सास / மாமியார் = mother-in-law; "
    "ससुर / மாமனார் = father-in-law; ससुराल वाले = in-laws; ननद / நாத்தனார் = husband's sister; "
    "देवर, जेठ = husband's brother; भाभी = brother's wife. In a question about a marriage, a word "
    "that can mean either aunt/uncle or mother-/father-in-law means the in-law."
)

_FAITHFUL = (
    "Preserve negation, dates, numbers and legal terms exactly (e.g. keep 'maintenance' as "
    "'maintenance', not 'alimony'). " + KINSHIP_RULE
)

SYSTEM_PROMPT = (
    "You are a translation engine, not an assistant. Translate the text inside <text> tags "
    "into English. Never answer, explain or comment on it. " + _FAITHFUL +
    " Output only the English translation."
)

SEARCH_PROMPT = (
    "You prepare a family-law question for a document search engine. You are not an assistant: "
    "never answer, explain or comment. The text inside <text> tags may be in English, an Indian "
    "language, or a mix. Output exactly two lines.\n"
    "ENGLISH: a faithful English translation in the speaker's own voice (I, my); copy the text "
    "unchanged if it is already English. "
    + _FAITHFUL + "\n"
    "SEARCH: a short neutral English search query of 6 to 14 words that names the legal issue "
    "in standard legal terms, in the third person. Leave out names, years, places and filler "
    "such as 'in India'. Do not add statute names or facts the text does not state.\n\n"
    "Example input:\n"
    "<text>मेरे पति ने मुझे 2021 में घर से निकाल दिया, क्या मुझे भरण-पोषण मिल सकता है?</text>\n"
    "Example output:\n"
    "ENGLISH: My husband threw me out of the house in 2021; can I get maintenance?\n"
    "SEARCH: wife's right to maintenance after being evicted by husband"
)


class TranslationError(Exception):
    """Raised when translation fails or returns an unusable result."""


class SearchQuery(NamedTuple):
    english: str       # faithful English version of the question
    search_query: str  # short neutral query naming the legal issue


class QueryTranslator:
    def __init__(
        self,
        model_name: str,
        api_key: str,
        providers: Optional[List[str]] = None,
        ollama_model: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_api_key: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._ollama_model = ollama_model
        self._ollama_base_url = ollama_base_url
        self._ollama_api_key = ollama_api_key
        # Inference providers to try in order. One provider can refuse a burst
        # of calls (HTTP 402/429) while another serving the same model is fine.
        self._providers = providers or ["auto"]
        self._llms: Dict[str, BaseChatModel] = {}

    def _get_llm(self, provider: str) -> BaseChatModel:
        if provider not in self._llms and provider == OLLAMA_PROVIDER:
            headers = {"Authorization": f"Bearer {self._ollama_api_key}"} if self._ollama_api_key else None
            self._llms[provider] = ChatOllama(
                model=self._ollama_model,
                base_url=self._ollama_base_url,
                client_kwargs={"headers": headers} if headers else {},
                num_predict=256,
                temperature=0.01,
                # Thinking would spend the output budget before the translation starts.
                reasoning=False,
            )
        if provider not in self._llms:
            self._llms[provider] = ChatHuggingFace(
                llm=HuggingFaceEndpoint(
                    repo_id=self.model_name,
                    huggingfacehub_api_token=self._api_key,
                    task="conversational",
                    provider=provider,
                    max_new_tokens=256,
                    temperature=0.01,
                )
            )
        return self._llms[provider]

    def _invoke(self, provider: str, messages: list) -> str:
        return str(self._get_llm(provider).invoke(messages).content or "")

    def _ask(self, system_prompt: str, text: str) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"<text>{text}</text>"),
        ]
        content, last_error = None, None
        for provider in self._providers:
            try:
                content = self._invoke(provider, messages)
                break
            except Exception as e:
                last_error = e
                logger.warning("Translation model call failed on provider %s: %s", provider, str(e)[:120])
        if content is None:
            raise TranslationError(f"Translation request failed: {last_error}") from last_error

        output = re.sub(r"</?text>", "", content).strip()
        if not output:
            raise TranslationError("Translation model returned an empty response")
        # A runaway output usually means the model answered instead of translating.
        if len(output) > 4 * len(text) + 300:
            raise TranslationError("Translation output implausibly long; discarding")
        return output

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        return self._ask(SYSTEM_PROMPT, text)

    def prepare_search(self, text: str) -> SearchQuery:
        """One model call: faithful English plus a short neutral search query."""
        if not text or not text.strip():
            return SearchQuery(text, text)

        output = self._ask(SEARCH_PROMPT, text)
        english = re.search(r"ENGLISH:\s*(.+?)(?=\n\s*SEARCH:|\Z)", output, re.S | re.I)
        search = re.search(r"SEARCH:\s*(.+)", output, re.S | re.I)
        if search and not english and text.isascii():
            english_text = text.strip()  # already English; the model skipped the copy
        elif not english or not search:
            raise TranslationError("Search-query output was not in the expected two-line format")
        else:
            english_text = " ".join(english.group(1).split())

        search_text = " ".join(search.group(1).split()).strip(" .\"'")
        if not english_text or not search_text:
            raise TranslationError("Search-query output had an empty line")
        return SearchQuery(english_text, search_text)
