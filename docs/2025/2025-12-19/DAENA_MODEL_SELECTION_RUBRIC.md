# Daena Model Selection Rubric

**Date**: 2025-12-19  
**Purpose**: Intelligent model selection to save tokens, improve speed, and maintain quality.

## Overview

Daena now uses a multi-tier model selection system:
1. **Deterministic Gate** - Handles trivial tasks without LLM
2. **Complexity Scorer** - Scores tasks 0-10 to determine tier
3. **Prompt Intelligence** - Optimizes prompts based on complexity
4. **Model Selection** - Chooses appropriate model for tier
5. **Cost Guard** - Enforces safety and cost limits

## Complexity Tiers

### Tier 0-2: NO_LLM
**Handled by**: Deterministic Gate  
**Examples**:
- Math: "2*2", "15% of 200"
- Time: "what time is it"
- JSON: "format this json", "extract keys"
- String: "uppercase hello", "word count"

**Result**: Immediate response, no LLM call

### Tier 3-5: CHEAP
**Model**: Local small model (qwen2.5:7b-instruct)  
**Examples**:
- Simple questions: "Hello, how are you?"
- Basic queries: "What departments do you manage?"
- Short conversations

**Result**: Fast, local, low-cost

### Tier 6-8: STRONG
**Model**: Local larger model or cloud (qwen2.5:14b-instruct, gpt-4o-mini)  
**Examples**:
- Complex questions: "Analyze the backend architecture"
- Multi-step tasks: "Compare department performance"
- Strategic queries: "Design a new workflow"

**Result**: Higher quality, still cost-effective

### Tier 9-10: DEEP_RESEARCH
**Model**: Strongest available (trained model, gpt-4o, claude-3-opus)  
**Examples**:
- Architecture audits: "Audit backend websocket security"
- Complex synthesis: "Design cross-department collaboration system"
- Production decisions: "Refactor streaming implementation"

**Result**: Highest quality, may use cloud if local insufficient

## Configuration

### Environment Variables

```bash
# Complexity Thresholds
DAENA_COMPLEXITY_NO_LLM_MAX=2      # 0-2: no LLM
DAENA_COMPLEXITY_CHEAP_MAX=5       # 3-5: cheap model
DAENA_COMPLEXITY_STRONG_MAX=8      # 6-8: strong model
# 9-10: deep research (no max)

# Deterministic Gate
DAENA_DETERMINISTIC_GATE_ENABLED=true

# Prompt Intelligence
PROMPT_BRAIN_ENABLED=true
PROMPT_BRAIN_MODE=rules            # rules|hybrid|llm_rewrite
PROMPT_BRAIN_COMPLEXITY_THRESHOLD=50

# Cost Guard
DAENA_FOUNDER_OVERRIDE=false       # Allow founder to force strong model
ENABLE_CLOUD_LLM=false             # Local-first by default
```

## How It Works

### Execution Flow

```
User Input
    ↓
[Deterministic Gate] → Handled? → Return immediately
    ↓ (not handled)
[Complexity Scorer] → Score 0-10 → Tier
    ↓
[Prompt Intelligence] → Optimize prompt (complexity-aware)
    ↓
[Model Selection] → Choose model based on tier
    ↓
[Cost Guard] → Safety checks
    ↓
[Provider Selection] → Local-first (Ollama) → Cloud (if enabled)
    ↓
[Execute LLM Call]
    ↓
[Return Response]
```

### Complexity Scoring Factors

**Increases Score**:
- Long input (>150 words: +4)
- Complex keywords (audit, architecture, security: +2 each)
- Multiple constraints (+1 per constraint)
- Production/multi-file context (+2)
- Finance/legal context (+1)
- Requires tools (+1)
- High priority (+1)

**Decreases Score**:
- Trivial patterns (hi, hello: -2)
- Very short input (<5 words: +0)

## Verification

### Test Scripts

1. **`scripts/test_no_llm_math.py`**
   - Verifies math operations handled without LLM
   - Expected: All pass

2. **`scripts/test_scoring.py`**
   - Verifies complexity scoring
   - Expected: Tiers match expectations

3. **`scripts/test_prompt_compiler_rules.py`**
   - Verifies deterministic prompt optimization
   - Expected: Same input → same output

4. **`scripts/test_local_ollama_path.py`**
   - Verifies local Ollama works
   - Expected: Response received if Ollama running

5. **`scripts/test_fallback_no_crash.py`**
   - Verifies safe fallback
   - Expected: Helpful message, no crash

### Health Endpoints

- `GET /api/v1/llm/active` - Shows active provider and why
- `GET /api/v1/llm/status` - Full provider status
- `POST /api/v1/llm/test` - Test LLM connectivity

## Examples

### Example 1: Math (No LLM)
```
Input: "what is 2*2"
Deterministic Gate: ✅ Handled
Result: "4" (immediate, no LLM call)
```

### Example 2: Simple Question (Cheap)
```
Input: "Hello, Daena. How are you?"
Complexity: Score 2 → Tier: CHEAP
Model: qwen2.5:7b-instruct (local)
Result: Fast, local response
```

### Example 3: Complex Task (Strong)
```
Input: "Analyze the backend architecture and identify security issues"
Complexity: Score 7 → Tier: STRONG
Model: qwen2.5:14b-instruct or gpt-4o-mini
Result: Higher quality analysis
```

### Example 4: Deep Research (Deep)
```
Input: "Audit the websocket implementation for security vulnerabilities and design improvements"
Complexity: Score 9 → Tier: DEEP_RESEARCH
Model: Best available (trained model or strongest cloud)
Result: Comprehensive analysis
```

## Cost Savings

### Before Rubric
- Every request → LLM call
- Trivial tasks → Unnecessary tokens
- No tier differentiation

### After Rubric
- Trivial tasks → No LLM (100% savings)
- Simple tasks → Small model (50-70% savings)
- Complex tasks → Appropriate model (quality maintained)

**Estimated Savings**: 30-50% reduction in LLM calls and tokens

## Safety

### Cost Guard Rules
1. **Cloud disabled** → Never call cloud (even if requested)
2. **Trivial task** → Block LLM call (use deterministic gate)
3. **Founder override** → Allow if `DAENA_FOUNDER_OVERRIDE=true`

### Logging
Every request logs:
- Complexity score and tier
- Provider and model used
- Estimated token count
- Cost estimate (if available)
- Decision reason

## Troubleshooting

### Issue: Math not handled
**Check**: `DAENA_DETERMINISTIC_GATE_ENABLED=true`

### Issue: All tasks use strong model
**Check**: Complexity thresholds in settings

### Issue: Cloud called when disabled
**Check**: `ENABLE_CLOUD_LLM=false` and cost guard logs

### Issue: Trivial tasks use LLM
**Check**: Deterministic gate is enabled and working

## Next Steps

1. Monitor complexity scores in production
2. Adjust thresholds based on usage patterns
3. Add more deterministic patterns as needed
4. Enhance prompt intelligence with complexity-aware optimization




