#!/bin/bash
# G9 - cold start must survive an unreachable package index.
#
# The block under test is EXTRACTED VERBATIM from the real startup.sh (lines from
# the INSTALL_RUNTIME_DEPS guard to the closing `fi`), so this cannot drift from
# what actually ships. `python3` is shimmed on PATH so that `pip` always fails,
# exactly as it would behind a flaky index, while every other python3 call is
# forwarded to the real interpreter.
set -uo pipefail

STARTUP_SH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/startup.sh"
WORK="$(mktemp -d)"
# Which interpreter stands in for python3 on the boot host. Defaults to whatever
# python3 is on PATH; CI overrides it with the project venv because a bare
# /usr/bin/python3 on some hosts has none of the app's dependencies.
REAL_PY="${LAWGPT_TEST_PYTHON:-$(command -v python3 || command -v python)}"
export REAL_PY
PASS=0; FAIL=0

say() { printf '%s\n' "$*"; }
check() {
    if [ "$2" = "0" ]; then printf '  [PASS] %s\n' "$1"; PASS=$((PASS+1))
    else printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL+1)); fi
}

# Extract the dependency block verbatim: from the INSTALL_RUNTIME_DEPS guard
# (line matching `if [ "${INSTALL_RUNTIME_DEPS`) through the `fi` at column 0
# that closes it. Derived from the file, not hard-coded.
extract_block() {
    local start end
    start="$(grep -n '^if \[ "\${INSTALL_RUNTIME_DEPS' "$STARTUP_SH" \
        | head -1 | cut -d: -f1)"
    [ -n "$start" ] || { echo "cannot locate INSTALL_RUNTIME_DEPS block" >&2; return 1; }
    end="$(awk -v s="$start" 'NR>s && /^fi[ ]*$/{print NR; exit}' "$STARTUP_SH")"
    [ -n "$end" ] || { echo "cannot locate closing fi" >&2; return 1; }
    echo "extracting startup.sh lines ${start}-${end}" >&2
    sed -n "${start},${end}p" "$STARTUP_SH"
}

# Build a stub site-packages so the "deps already importable" scenario is
# deterministic on ANY host, and a shim so `python3 -m pip` always fails.
STUB="$WORK/stubs"
mkdir -p "$STUB"
for m in fastapi uvicorn gunicorn openai pydantic; do
    printf '__version__ = "0.0.0-stub"\n' > "$STUB/$m.py"
done
# A stub importable app module so APP_MODULE="main:app" resolves.
printf 'app = object()\n' > "$STUB/main.py"

make_shim() {
    mkdir -p "$WORK/bin"
    cat > "$WORK/bin/python3" <<SHIM
#!/bin/bash
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pip" ]; then
    echo "pip: ERROR: Could not reach index https://pypi.org/simple/" >&2
    echo "pip: WARNING: Retrying (Retry after 3 seconds)" >&2
    exit 1
fi
exec "$REAL_PY" "\$@"
SHIM
    chmod +x "$WORK/bin/python3"
}

run_block() {
    # $1 = label, $2 = PIP_INSTALL_ATTEMPTS, $3 = SKIP_DEPS_IF_IMPORTABLE
    local out
    out="$WORK/out_$1.txt"
    (
        set -uo pipefail
        export CODE_DIR="$(mktemp -d)"
        printf 'fastapi>=0.100.0\n' > "$CODE_DIR/requirements.txt"
        export APP_MODULE="main:app"
        export INSTALL_RUNTIME_DEPS=true
        export PIP_INSTALL_ATTEMPTS="$2"
        export SKIP_DEPS_IF_IMPORTABLE="$3"
        # Scenario B must NOT see the stubs, so they are only on the path for
        # the scenario that claims deps are already present.
        if [ "$3" = "true" ]; then
            export PYTHONPATH="$STUB"
        else
            export PYTHONPATH="$WORK/empty"
        fi
        export PATH="$WORK/bin:$PATH"
        eval "$(extract_block)"
        echo "__BLOCK_RC=$?"
    ) > "$out" 2>&1
    printf '%s' "$out"
}

say "=============================================================="
say "G9 - cold start resilience (block extracted from startup.sh)"
say "=============================================================="
make_shim

say ""
say "[A] index unreachable, deps ALREADY importable -> must boot (rc=0)"
f="$(run_block a 3 true)"
sed 's/^/      /' "$f"
rc="$(grep -o '__BLOCK_RC=[0-9]*' "$f" | tail -1 | cut -d= -f2)"
check "block did not abort the boot" "$rc"
grep -q 'already importable; skipping pip install' "$f"
check "skipped the network install entirely" $?
grep -q 'Degraded boot OK\|deps already importable' "$f"
check "logged a clear start-up decision" $?

say ""
say "[B] index unreachable, deps MISSING -> must fail loudly (rc=1)"
# Make the REAL interpreter behave like one without the app's dependencies:
# a sitecustomize on PYTHONPATH strips site-packages at interpreter start, so
# both the skip-probe and the boot-verification see the same missing modules.
ISO="$WORK/isolated"
mkdir -p "$ISO"
cat > "$ISO/sitecustomize.py" <<'PY'
import sys
try:
    import site
    site.main()
except Exception:
    pass
sys.path[:] = [p for p in sys.path if "site-packages" not in p.replace("\\", "/")]
PY
outb="$WORK/out_b.txt"
(
    set -uo pipefail
    export CODE_DIR="$(mktemp -d)"
    printf 'fastapi>=0.100.0\n' > "$CODE_DIR/requirements.txt"
    export APP_MODULE="main:app"
    export INSTALL_RUNTIME_DEPS=true
    export PIP_INSTALL_ATTEMPTS=2
    export SKIP_DEPS_IF_IMPORTABLE=true
    export PYTHONPATH="$ISO"
    export PATH="$WORK/bin:$PATH"
    # Run the block in its own shell so `exit 1` is observable as a return code.
    bash -c "$(extract_block)"
) > "$outb" 2>&1
rcb=$?
sed 's/^/      /' "$outb"
printf '      (subshell exit code = %s)\n' "$rcb"
[ "$rcb" = "1" ]; check "exits 1 instead of booting a broken app" $?
grep -q 'FATAL: cannot boot' "$outb"; check "reports WHY it cannot boot" $?
grep -q 'Cannot continue' "$outb"; check "refuses to continue explicitly" $?

say ""
say "[C] no pip invocations at all when deps already resolve"
n="$(grep -c 'pip install attempt' "$WORK/out_a.txt" || true)"
[ "${n:-0}" = "0" ]; check "zero pip attempts (no index hit at all)" $?

say ""
say "=============================================================="
say "RESULT: $PASS passed, $FAIL failed"
rm -rf "$WORK"
[ "$FAIL" = "0" ]