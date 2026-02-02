#!/bin/bash
# test_awareness.sh — Verify Daena awareness fix (YES + DaenaBot Hands, no "don't have access")
# Run: chmod +x test_awareness.sh && ./test_awareness.sh
# Or from Git Bash on Windows: bash scripts/test_awareness.sh

BASE="${BASE_URL:-http://127.0.0.1:8000}"
echo "=== Testing Daena Awareness ==="
echo ""

echo "1. Checking capabilities API..."
CAPS=$(curl -s "$BASE/api/v1/capabilities" 2>/dev/null || curl -s "$BASE/api/v1/system/capabilities" 2>/dev/null)
if [ -z "$CAPS" ]; then
  echo "   ❌ FAIL: Could not reach capabilities API at $BASE"
else
  HANDS_STATUS=$(echo "$CAPS" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('hands_gateway',{}).get('status','?'))" 2>/dev/null || echo "?")
  echo "   DaenaBot Hands: $HANDS_STATUS"
fi
echo ""

echo "2. Testing chat awareness..."
RESPONSE=$(curl -s -X POST "$BASE/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Are you aware of your capabilities? Do you have access to my computer?"}' 2>/dev/null)

echo "   Response preview:"
echo "$RESPONSE" | python -c "import sys,json; d=json.load(sys.stdin); print((d.get('response') or d.get('message') or str(d))[:500])" 2>/dev/null || echo "$RESPONSE" | head -c 300
echo ""
echo ""

echo "3. Checking for wrong phrases..."
if echo "$RESPONSE" | grep -q "don't have access"; then
  echo "   ❌ FAIL: Still says 'don't have access'"
else
  echo "   ✓ PASS: Does not say 'don't have access'"
fi

if echo "$RESPONSE" | grep -qi "daenabot hands\|moltbot"; then
  echo "   ✓ PASS: Mentions DaenaBot Hands"
else
  echo "   ⚠ WARN: Does not mention DaenaBot Hands (check model/endpoint)"
fi

if echo "$RESPONSE" | grep -qi "yes"; then
  echo "   ✓ PASS: Says YES"
else
  echo "   ⚠ WARN: Does not say YES (check model/endpoint)"
fi

echo ""
echo "=== Test Complete ==="
