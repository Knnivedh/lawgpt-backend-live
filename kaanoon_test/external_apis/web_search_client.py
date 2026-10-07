
import requests
import re
import time
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from urllib.parse import urlparse

# Try to import Config, handling path issues
try:
    from config.config import Config
except ImportError:
    # If running as script or from subfolder, add root to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    try:
        from config.config import Config
    except ImportError:
        print("[WARNING] Could not import Config. API keys may not be loaded.")
        Config = None

try:
    from kaanoon_test.system_adapters.rag_system_adapter_ULTIMATE import SimpleWebSearchClient as _ParallelWebSearchClient
except Exception:
    _ParallelWebSearchClient = None

class WebSearchClient:
    """Advanced Web Search Client supporting multiple providers:
    1. Brave Search API (High quality, Free tier available)
    2. Serper.dev API (Google results, Free tier available)
    3. DuckDuckGo (Free, no key required)
    4. Fallback Scraper (Last resort)
    """

    DEFAULT_TRUSTED_DOMAINS = {
        "indiankanoon.org",
        "indiacode.nic.in",
        "main.sci.gov.in",
        "escr.supremecourt.gov.in",
        "livelaw.in",
        "barandbench.com",
        "scobserver.in",
        "lawcommissionofindia.nic.in",
        "egazette.nic.in",
        "dor.gov.in",
        "ibbi.gov.in",
        "rbi.org.in",
        "sebi.gov.in",
    }
    
    def __init__(self):
        self.providers = []
        self._parallel_client = None
        self.strict_trust_filter = str(
            os.getenv("LEGAL_TRUST_FILTER_STRICT", "true")
        ).strip().lower() in ("1", "true", "yes", "on")
        self.trusted_domains = self._load_trusted_domains()
        if _ParallelWebSearchClient is not None:
            try:
                self._parallel_client = _ParallelWebSearchClient()
                print("[INFO] WebSearch: advanced parallel search enabled.")
            except Exception as e:
                print(f"[WARNING] WebSearch: advanced parallel search unavailable ({e})")
        self._init_providers()

    def _load_trusted_domains(self) -> set:
        raw = str(os.getenv("LEGAL_TRUSTED_DOMAINS", "")).strip()
        if not raw:
            return set(self.DEFAULT_TRUSTED_DOMAINS)

        domains = {
            part.strip().lower()
            for part in raw.split(",")
            if part.strip()
        }
        return domains or set(self.DEFAULT_TRUSTED_DOMAINS)

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url or "")
            return (parsed.netloc or "").lower().replace("www.", "")
        except Exception:
            return ""

    def _is_trusted_domain(self, domain: str) -> bool:
        if not domain:
            return False

        for allowed in self.trusted_domains:
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True

        # Accept official Indian government and judiciary host patterns.
        return domain.endswith(".gov.in") or domain.endswith(".nic.in")

    def _apply_trust_filter(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not results:
            return []

        trusted: List[Dict[str, str]] = []
        untrusted: List[Dict[str, str]] = []

        for item in results:
            link = str(item.get("link") or item.get("url") or "").strip()
            domain = self._extract_domain(link)
            is_trusted = self._is_trusted_domain(domain)
            item["source_domain"] = domain
            item["trusted_source"] = is_trusted
            item["source_tier"] = "trusted" if is_trusted else "unverified"

            if is_trusted:
                trusted.append(item)
            else:
                untrusted.append(item)

        if trusted:
            return trusted if self.strict_trust_filter else trusted + untrusted

        return [] if self.strict_trust_filter else untrusted

    def _normalize_and_filter(self, results: List[Dict[str, Any]], default_source: str) -> List[Dict[str, str]]:
        normalized = [
            self._normalize_result(result, default_source)
            for result in results
            if isinstance(result, dict)
        ]
        normalized = [result for result in normalized if result.get("link")]

        # De-duplicate by URL before trust filtering.
        deduped = []
        seen = set()
        for result in normalized:
            key = result.get("link", "")
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(result)

        return self._apply_trust_filter(deduped)
        
    def _init_providers(self):
        """Initialize providers based on available keys."""
        # 1. Brave Search (Priority 1)
        if Config and Config.BRAVE_API_KEY:
            self.providers.append({
                "name": "Brave Search",
                "func": self._search_brave,
                "limit": 10
            })
            print("[INFO] WebSearch: Brave Search enabled.")
            
        # 2. Serper.dev (Priority 2)
        if Config and Config.SERPER_API_KEY:
            self.providers.append({
                "name": "Serper.dev",
                "func": self._search_serper,
                "limit": 10
            })
            print("[INFO] WebSearch: Serper.dev enabled.")
            
        # 3. DuckDuckGo (Priority 3 - Always available)
        try:
            # v8.x uses duckduckgo_search.DDGS, older versions used ddgs.DDGS
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS  # Fallback for older versions
                self.ddgs = DDGS()
            self.providers.append({
                "name": "DuckDuckGo",
                "func": self._search_ddgs,
                "limit": 5
            })
            print("[INFO] WebSearch: DuckDuckGo enabled.")
        except ImportError as e:
            print(f"[WARNING] WebSearch: duckduckgo-search not installed. ({e})")
            
        # 4. Fallback Scraper (Priority 4)
        self.providers.append({
            "name": "Fallback Scraper",
            "func": self._search_fallback,
            "limit": 3
        })

    def _normalize_result(self, result: Dict[str, Any], default_source: str = "Web Search") -> Dict[str, str]:
        url = str(result.get("url") or result.get("link") or result.get("href") or "").strip()
        domain = self._extract_domain(url)
        is_trusted = self._is_trusted_domain(domain)
        title = str(result.get("title") or result.get("name") or result.get("heading") or "").strip()
        snippet = str(
            result.get("snippet")
            or result.get("description")
            or result.get("body")
            or result.get("text")
            or ""
        ).strip()
        source = str(result.get("source") or default_source).strip()

        normalized = {
            "title": title,
            "link": url,
            "url": url,
            "snippet": snippet,
            "source": source,
            "source_domain": domain,
            "trusted_source": is_trusted,
            "source_tier": "trusted" if is_trusted else "unverified",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        for key in ("published", "image"):
            value = result.get(key)
            if value:
                normalized[key] = value

        return normalized

    def search_duckduckgo(self, query: str, max_results: int = 15) -> List[Dict[str, str]]:
        """Run the advanced parallel web search path when available."""
        if self._parallel_client is not None:
            try:
                results = self._parallel_client.search_duckduckgo(query, max_results=max_results)
                normalized = self._normalize_and_filter(results, "Advanced Parallel Search")
                if normalized:
                    print(f"[INFO] WebSearch: advanced parallel search returned {len(normalized)} results.")
                    return normalized[:max_results]
            except Exception as e:
                print(f"[WARNING] Advanced parallel search failed: {e}")

        if hasattr(self, "ddgs") and self.ddgs:
            try:
                results = self._search_ddgs(query, min(max_results, 10))
                if results:
                    return results[:max_results]
            except Exception as e:
                print(f"[WARNING] DuckDuckGo fallback search failed: {e}")

        return []

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform search using the best available provider.
        Iterates through providers until one succeeds.
        """
        advanced_results = self.search_duckduckgo(query, max_results=max_results)
        if advanced_results:
            return advanced_results

        for provider in self.providers:
            try:
                # print(f"[DEBUG] Trying provider: {provider['name']}")
                results = provider["func"](query, min(max_results, provider["limit"]))
                filtered_results = self._normalize_and_filter(results, provider["name"])
                if filtered_results:
                    # print(f"[INFO] Search successful with {provider['name']}")
                    return filtered_results[:max_results]
            except Exception as e:
                print(f"[WARNING] Provider {provider['name']} failed: {e}")
                continue
                
        print("[ERROR] All search providers failed.")
        return []

    def _search_brave(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Search using Brave Search API."""
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": Config.BRAVE_API_KEY
        }
        params = {"q": query, "count": max_results}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Brave API returned {response.status_code}")
            
        data = response.json()
        results = []
        
        if "web" in data and "results" in data["web"]:
            for item in data["web"]["results"]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "source": "Brave Search"
                })
        return results

    def _search_serper(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Search using Serper.dev API (Google results)."""
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": Config.SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"q": query, "num": max_results}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Serper API returned {response.status_code}")
            
        data = response.json()
        results = []
        
        if "organic" in data:
            for item in data["organic"]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "Serper.dev (Google)"
                })
        return results

    def _search_ddgs(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Search using duckduckgo-search library."""
        results = []
        # DDGS text search
        ddgs_gen = self.ddgs.text(query, max_results=max_results)
        for r in ddgs_gen:
            results.append({
                "title": r.get("title", ""),
                "link": r.get("href", ""),
                "snippet": r.get("body", ""),
                "source": "DuckDuckGo"
            })
        return results

    def _search_fallback(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Fallback HTML scraping."""
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Fallback scraper returned {response.status_code}")
            
        html = response.text
        
        # Basic regex parsing
        link_pattern = r'<a class="result__a" href="([^"]+)">([^<]+)</a>'
        snippet_pattern = r'<a class="result__snippet"[^>]*>(.*?)</a>'
        
        links = re.findall(link_pattern, html)
        snippets = re.findall(snippet_pattern, html)
        
        for i in range(min(len(links), len(snippets), max_results)):
            link_url = links[i][0]
            title = links[i][1]
            snippet = snippets[i]
            
            # Clean up HTML entities
            title = self._clean_html(title)
            snippet = self._clean_html(snippet)
            
            results.append({
                "title": title,
                "link": link_url,
                "snippet": snippet,
                "source": "Web Search (Fallback)"
            })
        return results
        
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and entities."""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&#x27;', "'").replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()

# Singleton
_web_client = None

def get_web_search_client() -> WebSearchClient:
    global _web_client
    if _web_client is None:
        _web_client = WebSearchClient()
    return _web_client
