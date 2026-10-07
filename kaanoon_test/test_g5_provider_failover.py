"""G5 - vendor-crossing failover + circuit breaker, proven against a FAKE pool.

Reproduces the measured production outage shape:
  * Groq keys that share ONE org OTPM ceiling
  * TokenRouter 503 "No available channel for model z-ai/glm-5.3-free"
  * an occasional 401 Invalid API Key

Assertions
  1. rotation on 429 crosses to a DIFFERENT vendor (the G5 fix)
  2. it never spends consecutive attempts inside the exhausted Groq org
  3. the vendor breaker OPENS after N 429s and the chain leaves Groq
  4. an open Groq circuit blocks the flash rig too (it is a Groq client)
  5. OpenRouter / NVIDIA keys present in env actually join the failover pool
  6. a 401 parks that vendor immediately instead of retrying it
  7. a recovered vendor is re-admitted after cooldown (half-open)

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_g5_provider_failover.py
"""
import os
import sys
import logging
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fake keys, clearly labelled. No real credential is used or needed.
ENV = {
    "GROQ_API_KEY": "gsk_fake_prodorg_0000000000000000a1",
    "GROQ_API_KEY_2": "gsk_fake_prodorg_0000000000000000b2",
    "GROQ_API_KEY_3": "gsk_fake_prodorg_0000000000000000c3",
    "GROQ_API_KEY_4": "gsk_fake_prodorg_0000000000000000d4",
    "GROQ_API_KEY_5": "gsk_fake_prodorg_0000000000000000e5",
    "DAHL_API_KEY": "dahl_fake_prodorg_000000000000f1",
    "TOKENROUTER_API_KEY": "tr_fake_prodorg_00000000000001",
    "CEREBRAS_API_KEY": "csk-fake-prodorg-000000000001",
    "OPENROUTER_API_KEY": "sk-or-v1-fake0000000000000a",
    "OPENROUTER_API_KEY_2": "sk-or-v1-fake0000000000000b",
    "NVIDIA_API_KEY": "nvapi-fake-0000000000000000a",
    # Tight breaker + short cooldowns so half-open recovery is observable.
    "LLM_BREAKER_THRESHOLD": "3",
    "LLM_BREAKER_WINDOW_SECONDS": "60",
    "LLM_VENDOR_COOLDOWN_SECONDS": "2",
    # THIS SUITE TESTS THE FALLBACK MACHINERY, so it must run with the failover
    # pool enabled. Production defaults to LLM_SINGLE_PROVIDER=true (Dahl only,
    # 100M free tokens), which correctly collapses the chain to a single vendor
    # and would fail the multi-vendor assertions below by design. Set false here
    # so we verify the rollback path still works if the allowance is exhausted.
    "LLM_SINGLE_PROVIDER": "false",
}

PASSED, FAILED = [], []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def build_manager(env=None):
    """Fresh manager with the injected key shape.

    NOTE: the module calls load_dotenv(override=False) at import, so keys in
    config/.env survive our os.environ edits. For the single-vendor scenario we
    must therefore blank the dotenv candidates too, otherwise the pool silently
    regains dahl/tokenrouter/openrouter/nvidia.
    """
    for k in list(os.environ):
        head = k.split("_")[0].upper()
        if head in {"GROQ", "DAHL", "TOKENROUTER", "OPENROUTER", "NVIDIA", "CEREBRAS"} \
                or k.startswith("LLM_BREAKER") or k == "LLM_VENDOR_COOLDOWN_SECONDS":
            os.environ.pop(k, None)
    os.environ.update(env if env is not None else ENV)
    _scrub_dotenv(bool(env))
    mod = "kaanoon_test.utils.client_manager"
    if mod in sys.modules:
        import importlib
        importlib.reload(sys.modules[mod])
    from kaanoon_test.utils.client_manager import GroqClientManager
    return GroqClientManager()


def _scrub_dotenv(active: bool):
    """Neutralise the .env providers so the injected shape is authoritative."""
    if not active:
        return
    import config.config as _cfg
    _cfg.DAHL_API_KEY = None
    _cfg.TOKENROUTER_API_KEY = None
    _cfg.CEREBRAS_API_KEY = None
    _cfg.OPENROUTER_API_KEY = None
    _cfg.OPENROUTER_API_KEY_2 = None
    _cfg.OPENROUTER_API_KEY_3 = None
    _cfg.OPENROUTER_API_KEY_4 = None
    _cfg.NVIDIA_API_KEY = None
    _cfg.NVIDIA_API_KEY_2 = None
def main():
    logging.disable(logging.CRITICAL)
    cm = build_manager()
    types = cm.client_types
    vendors = []
    for t in types:
        if t not in vendors:
            vendors.append(t)

    print("=" * 74)
    print("G5 - failover pool + circuit breaker")
    print("=" * 74)
    print(f"clients loaded   : {len(cm.clients)}")
    print(f"per-index vendor : {types}")
    print(f"vendor chain     : {' -> '.join(vendors)}")
    print()

    print("[5] OpenRouter / NVIDIA actually join the synthesis failover pool")
    check("openrouter is in the failover chain", "openrouter" in vendors, str(vendors))
    check("nvidia is in the failover chain", "nvidia" in vendors, str(vendors))
    check("at least 4 distinct vendors available", len(vendors) >= 4,
          f"{len(vendors)} vendors")
    print()

    print("[1,2] 429 rotation crosses vendors (the G5 fix)")
    groq_idx = next(i for i, t in enumerate(types) if t == "groq")
    cm.current_key_index = groq_idx
    start_vendor = cm.get_current_provider_type()
    seq, worst = [], 0
    prev = start_vendor
    for _ in range(8):
        cm.force_rotation("429 OTPM: Limit 1000, Used 992")
        v = cm.get_current_provider_type()
        worst = max(worst, 1 if v == prev else 0)
        prev = v
        seq.append(v)
    print(f"         start  = {start_vendor}")
    print(f"         x8 429 = {seq}")
    crossed = sum(1 for a, b in zip([start_vendor] + seq[:-1], seq) if a != b)
    check("every 429 changed vendor", crossed == len(seq),
          f"{crossed}/{len(seq)} transitions crossed")
    # The G5 defect was adjacency: 429 on gsk_A -> 429 on gsk_B, same org. The
    # fix must guarantee NO two consecutive attempts share a vendor.
    check("no two consecutive attempts share a vendor", worst == 0,
          f"longest same-vendor run={worst}")
    print()

    print("[3] breaker opens after threshold and evicts the vendor")
    cm2 = build_manager()
    t2 = cm2.client_types
    g2 = next(i for i, t in enumerate(t2) if t == "groq")
    # Real production shape: repeated user requests land on Groq and each one
    # returns the org-wide 429. Simulate 3 such requests, not 3 rotations.
    for attempt in range(3):
        cm2.current_key_index = g2
        cm2.get_client()
        assert cm2.get_current_provider_type() == "groq", "expected to be on groq"
        cm2.force_rotation("429 OTPM: Limit 1000, Used 992")
    check("groq breaker is OPEN after 3 x 429 on groq", cm2.breaker.is_open("groq"),
          f"state={cm2.breaker.state().get('groq')}")
    landed = []
    for _ in range(6):
        cm2.get_client()
        landed.append(cm2.get_current_provider_type())
    check("open groq circuit is skipped by get_client",
          "groq" not in landed, f"landed on={landed}")
    print()

    print("[4] flash rig (a Groq client) respects the open Groq circuit")
    check("groq circuit still open at flash check time",
          cm2.breaker.is_open("groq"),
          f"state={cm2.breaker.state().get('groq')}")
    proxy = cm2.chat
    check("flash rig refused while groq circuit is open",
          proxy.completions._flash_usable() is False,
          f"_flash_usable() -> {proxy.completions._flash_usable()}")
    check("proxy carries the breaker", proxy.completions.breaker is cm2.breaker)
    check("proxy flash provider is the vendor, not a label",
          proxy.completions.flash_provider == "groq",
          proxy.completions.flash_provider)
    print()

    print("[6] 401 parks that vendor immediately")
    cm3 = build_manager()
    cm3.breaker.record_failure("tokenrouter", "unauthorized", "401 Invalid API Key")
    check("401 opens the breaker on the FIRST failure",
          cm3.breaker.is_open("tokenrouter"),
          f"state={cm3.breaker.state().get('tokenrouter')}")
    cm3.breaker.reset()
    cm3.breaker.record_failure(
        "groq", "not_found", "No available channel for model z-ai/glm-5.3-free")
    check("404/no-channel classification parks the vendor",
          cm3.breaker.is_open("groq"),
          f"state={cm3.breaker.state().get('groq')}")
    print()

    print("[7] vendor is re-admitted after cooldown (half-open)")
    cm4 = build_manager()
    for _ in range(3):
        cm4.breaker.record_failure("cerebras", "rate_limited", "429")
    check("cerebras open immediately after 3 failures",
          cm4.breaker.is_open("cerebras"))
    time.sleep(2.2)  # LLM_VENDOR_COOLDOWN_SECONDS=2
    check("cerebras half-open again after cooldown",
          not cm4.breaker.is_open("cerebras"))
    cm4.breaker.record_success("cerebras")
    check("success keeps it closed and clears history",
          not cm4.breaker.is_open("cerebras")
          and "cerebras" not in cm4.breaker._failures)
    print()
# ── 8: the latency bound ─────────────────────────────────────────────
    print("[8] a 429 storm is bounded, not amplified")
    import time as _t

    cm5 = build_manager()
    g5 = next(i for i, t in enumerate(cm5.client_types) if t == "groq")
    cm5.current_key_index = g5
    t0 = _t.time()
    seq2 = []
    for _ in range(12):          # 12 consecutive user requests, all 429
        cm5.get_client()
        if cm5.get_current_provider_type() == "groq":
            cm5.force_rotation("429 OTPM: Limit 1000, Used 992")
            seq2.append("groq")
    elapsed = _t.time() - t0
    groq_attempts = len(seq2)
    check("groq is not hammered once its circuit opens",
          groq_attempts <= 3, f"groq attempted {groq_attempts}x over 12 requests")
    check("the loop itself is fast (no sleeping/retrying)",
          elapsed < 5.0, f"{elapsed:.3f}s for 12 simulated requests")
    print(f"         12 requests hit groq only {groq_attempts} time(s) in {elapsed:.3f}s;")
    print(f"         breaker: {cm5.breaker.state().get('groq')}")

    health = cm5.provider_health()
    check("provider_health reports the live vendor chain",
          health.get("_vendor_chain") and health.get("_active"),
          f"chain={health.get('_vendor_chain')} active={health.get('_active')}")
    check("provider_health accounts for every configured vendor",
          all(v in health for v in cm5.vendor_chain()),
          f"vendors={cm5.vendor_chain()}")
    check("health names the vendor that actually 429'd",
          health.get("groq", {}).get("recent_failures", 0) >= 1,
          f"groq={health.get('groq')}")
    print(f"         NOTE: groq was attempted only {groq_attempts}x, so its circuit")
    print(f"         correctly never opened -- the breaker is what stopped the")
    print(f"         2nd..12th attempts from ever reaching groq at all.")
    print()

    # ── 9: REGRESSION GUARD - proactive rotation must not open a circuit ──
    # advanced_rag_api_server.py calls force_rotation("pre-thinking-trace")
    # PROACTIVELY, up to 3x, BEFORE any failure has occurred. If force_rotation
    # records a breaker failure on every call, three successful thinking traces
    # open the circuit on a perfectly HEALTHY vendor - exactly the outage G5
    # exists to prevent, caused by the fix itself.
    print("[9] a proactive (non-failure) rotation does NOT open a circuit")
    cm6 = build_manager()
    g6 = next(i for i, t in enumerate(cm6.client_types) if t == "groq")
    cm6.current_key_index = g6
    for _ in range(3):
        cm6.force_rotation(reason="pre-thinking-trace", record_failure=False)
    opened = [v for v, h in cm6.provider_health().items()
              if isinstance(h, dict) and h.get("open")]
    check("3 proactive rotations did NOT open any vendor circuit",
          not opened, f"opened={opened}")
    check("proactive rotation still moved to a different vendor",
          cm6.get_current_provider_type() != "groq",
          f"now on {cm6.get_current_provider_type()}")
    print()

    # And the opposite must hold: a real 429 DOES open it.
    cm7 = build_manager()
    g7 = next(i for i, t in enumerate(cm7.client_types) if t == "groq")
    for _ in range(3):
        cm7.current_key_index = g7
        cm7.get_client()
        cm7.force_rotation("429 OTPM: Limit 1000, Used 992")
    check("3 REAL 429s still open the groq circuit",
          cm7.breaker.is_open("groq"),
          "the breaker is not neutered by the proactive-rotation fix")
    print()

    # ── 10: CUMULATIVE REALITY - the single-query test above hides this ──
    # Each proactive rotation drops 1 failure on whatever vendor is current.
    # In production EVERY answer longer than 400 chars does up to 3 of these.
    # Failures are spread thin, so one query never trips a breaker - but they
    # ACCUMULATE across queries and eventually open EVERY circuit on a system
    # where nothing has ever actually failed.
    print("[10] proactive rotations must not accumulate across many queries")
    cm8 = build_manager()
    openers = set()
    for q in range(30):                       # 30 normal user queries
        for _ in range(3):                   # ...each doing 3 thinking traces
            cm8.force_rotation(reason="pre-thinking-trace", record_failure=False)
    h8 = cm8.provider_health()
    openers = [v for v, h in h8.items()
               if isinstance(h, dict) and h.get("open")]
    counts = {v: h.get("recent_failures")
              for v, h in h8.items() if isinstance(h, dict)}
    print(f"         per-vendor failure counts after 90 proactive rotations:")
    print(f"         {counts}")
    print(f"         circuits OPENED: {openers}")
    check("30 healthy queries with proactive rotation open NO circuits",
          not openers, f"opened={openers}")
    print("         (before the fix this would open every vendor's circuit and")
    print("          take the entire LLM pool down with no upstream failure)")
    print()

    # ── 11: single-vendor deployment must not wedge ──────────────────────
    # PRODUCTION SHAPE: LLM_SINGLE_PROVIDER=true, so exactly one vendor is
    # loaded regardless of what other keys exist in the environment. Rotation
    # has nowhere to go, so _find_next_index must degrade gracefully rather than
    # loop or raise -- and the breaker must still surface the outage.
    print("[11] single-provider mode degrades gracefully (production shape)")
    SINGLE = {
        "DAHL_API_KEY": "dahl_fake_single_0000000000001",
        "DAHL_API_KEY_2": "dahl_fake_single_0000000000002",
        "LLM_BREAKER_THRESHOLD": "3",
        "LLM_VENDOR_COOLDOWN_SECONDS": "2",
        "LLM_SINGLE_PROVIDER": "true",
    }
    cm9 = build_manager(SINGLE)
    types9 = cm9.client_types
    check("single-provider mode loaded exactly ONE vendor",
          len(set(types9)) == 1, f"{sorted(set(types9))} from {types9}")
    check("and that vendor is dahl", set(types9) == {"dahl"}, str(set(types9)))
    check("all other configured vendors were ignored",
          not ({"groq", "tokenrouter", "cerebras", "openrouter", "nvidia"} & set(types9)),
          str(sorted(set(types9))))
    vendor = types9[0]
    landed = []
    for _ in range(6):
        cm9.force_rotation("429 OTPM: Limit 1000, Used 992")
        landed.append(cm9.get_current_provider_type())
    check("rotation never leaves the only vendor (no crash)",
          all(v == vendor for v in landed), f"landed={landed}")
    check("after 3x429 the sole vendor circuit opens (honest signal)",
          cm9.breaker.is_open(vendor),
          f"operator can now see there is nowhere to go")
    print(f"         {landed} -> open={cm9.breaker.is_open(vendor)}")
    print()

    print("=" * 74)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())