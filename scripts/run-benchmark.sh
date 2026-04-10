#!/usr/bin/env bash
# =============================================================
# Daena — Intelligence Benchmark Runner
# =============================================================
# Runs Daena's pipeline ON vs OFF comparison on standard benchmarks.
#
# Usage:
#   ./scripts/run-benchmark.sh              # Quick (15 challenges, ~5 min)
#   ./scripts/run-benchmark.sh --full       # Full suite (~30 min)
#   ./scripts/run-benchmark.sh --gpqa       # GPQA Diamond subset
#   ./scripts/run-benchmark.sh --humaneval  # HumanEval coding
#
# Requirements:
#   - Daena backend running (start-daena.sh)
#   - At least one LLM available (vLLM, Ollama, or API key)
# =============================================================

set -euo pipefail

BACKEND_URL="${DAENA_BACKEND_URL:-http://localhost:8000}"
API="$BACKEND_URL/api/v1"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} DAENA — Intelligence Benchmark${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Check backend is running
if ! curl -s "$BACKEND_URL/api/v1/health" > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Backend not reachable at $BACKEND_URL${NC}"
    echo "        Start Daena first: ./start-daena.sh"
    exit 1
fi
echo -e "${GREEN}Backend running at $BACKEND_URL${NC}"

# Check what LLMs are available
echo ""
echo -e "${YELLOW}Available runtimes:${NC}"
curl -s "$API/runtimes" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for rt in data.get('runtimes', data) if isinstance(data, dict) else data:
    name = rt.get('runtime_id', rt.get('name', '?'))
    status = rt.get('status', '?')
    print(f'  {name}: {status}')
" 2>/dev/null || echo "  (could not fetch runtimes)"

# Start benchmark
echo ""
echo -e "${CYAN}Starting intelligence benchmark...${NC}"
echo "  This runs 15+ challenges through:"
echo "    A) Raw single-model inference (baseline)"
echo "    B) Daena's 21-stage Laevateinn pipeline"
echo ""

RESULT=$(curl -s -X POST "$API/benchmark/intelligence" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $(cat ~/.daena-token 2>/dev/null || echo 'dev-token')")

JOB_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}Failed to start benchmark. Response:${NC}"
    echo "$RESULT"
    exit 1
fi

echo -e "Job ID: ${GREEN}$JOB_ID${NC}"
echo ""

# Poll for results
echo -e "${YELLOW}Running...${NC}"
while true; do
    RESP=$(curl -s "$API/benchmark/intelligence/$JOB_ID")
    STATUS=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)

    if [ "$STATUS" = "complete" ]; then
        break
    elif [ "$STATUS" = "failed" ]; then
        echo -e "${RED}Benchmark failed.${NC}"
        echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
        exit 1
    fi

    COMPLETED=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d.get('completed',0)}/{d.get('total_challenges',0)}\")" 2>/dev/null)
    echo -ne "\r  Progress: $COMPLETED challenges    "
    sleep 5
done
echo ""

# Display results
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${GREEN} BENCHMARK RESULTS${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

echo "$RESP" | python3 -c "
import json, sys

d = json.load(sys.stdin)
report = d.get('comparison_report', d)

off = report.get('pipeline_off_avg', d.get('pipeline_off_avg', 0))
on = report.get('pipeline_on_avg', d.get('pipeline_on_avg', 0))
delta = report.get('overall_delta', d.get('overall_delta', 0))
total = report.get('total_challenges', d.get('total_challenges', 0))

print(f'  Pipeline OFF (baseline): {off:.1f}/10')
print(f'  Pipeline ON  (Daena):    {on:.1f}/10')
print(f'  Intelligence Delta:      {delta:+.1f}')
print(f'  Total Challenges:        {total}')
print()

# Per-category
cats = report.get('per_category', d.get('per_category', {}))
if cats:
    print('  Category Breakdown:')
    print('  ' + '-' * 50)
    for cat, scores in cats.items():
        cat_off = scores.get('off', scores.get('pipeline_off_avg', 0))
        cat_on = scores.get('on', scores.get('pipeline_on_avg', 0))
        cat_delta = scores.get('delta', scores.get('overall_delta', 0))
        winner = 'Pipeline' if cat_delta > 0 else 'Baseline' if cat_delta < 0 else 'Tied'
        print(f'    {cat:15s}  OFF={cat_off:.1f}  ON={cat_on:.1f}  delta={cat_delta:+.1f}  ({winner})')
    print()

verdict = report.get('verdict', '')
if verdict:
    print(f'  Verdict: {verdict}')
" 2>/dev/null || echo "$RESP" | python3 -m json.tool

echo ""
echo -e "${CYAN}============================================${NC}"
echo ""
