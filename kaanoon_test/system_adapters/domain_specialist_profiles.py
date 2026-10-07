"""Compatibility layer for legacy agentic RAG deployments.

Older runtime snapshots imported profile constants and helper functions from this
module. The current codebase no longer depends on it directly, but the deployed
container can still boot older code paths, so keep a tolerant fallback here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable


@dataclass(frozen=True)
class LegacyDomainProfile:
    name: str
    title: str
    prompt: str
    keywords: tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "prompt": self.prompt,
            "keywords": list(self.keywords),
        }

    def __call__(self, *args: Any, **kwargs: Any) -> "LegacyDomainProfile":
        return self

    def __getitem__(self, key: str) -> Any:
        return self.as_dict().get(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)


GENERAL_PROFILE = LegacyDomainProfile(
    name="general",
    title="General Legal Analysis",
    prompt="Provide a grounded Indian legal analysis with statutes, issues, and sources.",
    keywords=("general", "legal", "analysis"),
)

EMPLOYMENT_PROFILE = LegacyDomainProfile(
    name="employment",
    title="Employment Law",
    prompt="Focus on employment, service rules, misconduct, termination, salary, and workplace remedies.",
    keywords=("employment", "employee", "employer", "salary", "termination", "workplace"),
)

CRIMINAL_PROFILE = LegacyDomainProfile(
    name="criminal",
    title="Criminal Law",
    prompt="Focus on offences, intent, mens rea, FIR, bail, procedure, and criminal liability.",
    keywords=("criminal", "theft", "bail", "fir", "mens rea", "intent"),
)

PROPERTY_PROFILE = LegacyDomainProfile(
    name="property",
    title="Property Law",
    prompt="Focus on ownership, possession, sale deeds, title, tenancy, and property remedies.",
    keywords=("property", "possession", "sale deed", "title", "tenancy"),
)

FAMILY_PROFILE = LegacyDomainProfile(
    name="family",
    title="Family Law",
    prompt="Focus on divorce, custody, maintenance, alimony, and domestic-relations remedies.",
    keywords=("divorce", "custody", "maintenance", "alimony", "family"),
)

CONSUMER_PROFILE = LegacyDomainProfile(
    name="consumer",
    title="Consumer Law",
    prompt="Focus on deficiency in service, unfair trade practice, compensation, and consumer remedies.",
    keywords=("consumer", "deficiency", "unfair trade practice", "refund", "compensation"),
)

CONSTITUTIONAL_PROFILE = LegacyDomainProfile(
    name="constitutional",
    title="Constitutional Law",
    prompt="Focus on constitutional rights, writs, judicial review, and fundamental freedoms.",
    keywords=("constitutional", "fundamental right", "writ", "article", "judicial review"),
)

DOMAIN_SPECIALIST_PROFILES: Dict[str, LegacyDomainProfile] = {
    profile.name: profile
    for profile in (
        GENERAL_PROFILE,
        EMPLOYMENT_PROFILE,
        CRIMINAL_PROFILE,
        PROPERTY_PROFILE,
        FAMILY_PROFILE,
        CONSUMER_PROFILE,
        CONSTITUTIONAL_PROFILE,
    )
}

DOMAIN_SPECIALIST_ORDER = list(DOMAIN_SPECIALIST_PROFILES.keys())
DEFAULT_DOMAIN_PROFILE = GENERAL_PROFILE


def _normalize_domain_name(domain: Any) -> str:
    text = (domain or "general")
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().lower().replace(" ", "_")
    return text or "general"


def get_domain_specialist_profile(domain: Any = None) -> LegacyDomainProfile:
    return DOMAIN_SPECIALIST_PROFILES.get(_normalize_domain_name(domain), DEFAULT_DOMAIN_PROFILE)


def get_domain_specialist_prompt(domain: Any = None) -> str:
    return get_domain_specialist_profile(domain).prompt


def resolve_domain_specialist(domain: Any = None) -> LegacyDomainProfile:
    return get_domain_specialist_profile(domain)


def iter_domain_specialist_profiles() -> Iterable[LegacyDomainProfile]:
    return DOMAIN_SPECIALIST_PROFILES.values()


def __getattr__(name: str) -> Any:
    if name in globals():
        return globals()[name]
    if name.endswith("_PROFILES") or name.endswith("_PROFILE_MAP"):
        return DOMAIN_SPECIALIST_PROFILES
    if name.startswith("get_"):
        return get_domain_specialist_profile if "prompt" not in name.lower() else get_domain_specialist_prompt
    if name.startswith("resolve_"):
        return resolve_domain_specialist
    if name.isupper() and name.endswith("_PROFILE"):
        return DEFAULT_DOMAIN_PROFILE
    return DEFAULT_DOMAIN_PROFILE


__all__ = [
    "LegacyDomainProfile",
    "GENERAL_PROFILE",
    "EMPLOYMENT_PROFILE",
    "CRIMINAL_PROFILE",
    "PROPERTY_PROFILE",
    "FAMILY_PROFILE",
    "CONSUMER_PROFILE",
    "CONSTITUTIONAL_PROFILE",
    "DOMAIN_SPECIALIST_PROFILES",
    "DOMAIN_SPECIALIST_ORDER",
    "DEFAULT_DOMAIN_PROFILE",
    "get_domain_specialist_profile",
    "get_domain_specialist_prompt",
    "resolve_domain_specialist",
    "iter_domain_specialist_profiles",
]