"""Hosted embeddings client for Hugging Face Inference API."""

import os
from typing import Any, List

import requests


class HuggingFaceEmbeddingClient:
    """Create embeddings without loading the model into the web process."""

    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.endpoint = (
            "https://router.huggingface.co/hf-inference/models/"
            f"{model_name}"
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("HUGGINGFACE_API_KEY must be set for embeddings")

        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=120,
        )
        response.raise_for_status()
        vectors = self._parse_vectors(response.json())

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Hugging Face returned {len(vectors)} embeddings for {len(texts)} texts"
            )
        for vector in vectors:
            if len(vector) != self.dimension:
                raise RuntimeError(
                    f"Expected {self.dimension}-dimensional embedding, got {len(vector)}"
                )
        return vectors

    def _parse_vectors(self, payload: Any) -> List[List[float]]:
        """Accept sentence vectors and token-level feature-extraction output."""
        if isinstance(payload, dict) and "error" in payload:
            raise RuntimeError(f"Hugging Face embedding error: {payload['error']}")

        if not isinstance(payload, list) or not payload:
            raise RuntimeError("Hugging Face returned an invalid embedding response")

        if isinstance(payload[0], (int, float)):
            return [payload]

        if isinstance(payload[0], list) and payload[0] and isinstance(payload[0][0], (int, float)):
            return payload

        if isinstance(payload[0], list):
            return [
                [sum(values) / len(values) for values in zip(*token_vectors)]
                for token_vectors in payload
            ]

        raise RuntimeError("Hugging Face returned an unsupported embedding shape")