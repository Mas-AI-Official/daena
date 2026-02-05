# DAENA PROJECT: QUICK START GUIDE

## 📋 WHAT YOU NEED TO DO

Your Daena project has **massive potential** but significant gaps between vision and reality. This guide gives you the exact steps to bridge that gap.

## 🚨 CRITICAL PRIORITY ORDER

### **PHASE 1: SECURITY (DO THIS FIRST!)**
**Status**: ❌ Critical vulnerabilities  
**Timeline**: 1 week

1. Open Cursor/Antigravity in your Daena repo
2. Copy-paste `CURSOR_PROMPT_1_SECURITY.md` into Cursor
3. Let it implement all security fixes
4. Test that unauthorized access is blocked
5. Verify secrets are in credential vault, not plain text

**Why first?** Your current setup has auth disabled and allows arbitrary code execution. You MUST fix this before doing anything else.

---

### **PHASE 2: CORE FUNCTIONALITY**
**Status**: ❌ DaenaBot Hands missing  
**Timeline**: 2-3 weeks

1. Run `CURSOR_PROMPT_2_DAENABOT_HANDS.md` to create Hands service
2. Run `CURSOR_PROMPT_3_FRONTEND_BACKEND_SYNC.md` to wire frontend
3. Test end-to-end: Click button → Daena takes screenshot
4. Verify approvals work

**Why second?** Without this, Daena can't actually DO anything outside the backend.

---

### **PHASE 3: CLEANUP & OPTIMIZATION**
**Status**: ⚠️ Lots of duplicates  
**Timeline**: 1 week

1. Run `CURSOR_PROMPT_4_CLEANUP.md` to clean up repo
2. Set up Ollama models (see below)
3. Configure hybrid routing
4. Test cost savings

**Why third?** Clean repo = easier maintenance. Hybrid routing = cost savings.

---

### **PHASE 4: ADVANCED FEATURES**
**Status**: ⚠️ Partially implemented  
**Timeline**: 2-3 weeks

1. Run `CURSOR_PROMPT_5_TWO_COUNCIL_SYSTEM.md`
2. Wire NBMF Memory fully
3. Enable E-DNA learning
4. Test councils make decisions

**Why last?** Build solid foundation first, then add advanced features.

---

## 🖥️ OLLAMA SETUP FOR YOUR HARDWARE

Your XPS 16 has RTX 4060 (8GB VRAM) + 32GB RAM. Here's the optimal setup:

```bash
# Install Ollama
# Windows: Download from https://ollama.com
# Mac/Linux: curl -fsSL https://ollama.com/install.sh | sh

# Pull models (total ~50GB disk)
ollama pull qwen2.5-coder:14b-instruct   # Main model (fits in 8GB VRAM)
ollama pull gemma2:9b                    # Fast model
ollama pull llava:13b                    # Vision model
ollama pull llama3.3:70b-q4_K_M          # Fallback reasoning (quantized)

# Test
ollama run qwen2.5-coder:14b-instruct "Write a Python function to calculate fibonacci"
```

Update your `.env`:
```env
DEFAULT_LOCAL_MODEL=qwen2.5-coder:14b-instruct
OLLAMA_REASONING_MODEL=llama3.3:70b-q4_K_M
OLLAMA_VISION_MODEL=llava:13b
OLLAMA_FAST_MODEL=gemma2:9b
LOCAL_FIRST=true
CLOUD_FALLBACK_ENABLED=true
CLOUD_REASONING_MODEL=claude-3-5-sonnet-latest
MAX_DAILY_COST_USD=5.00  # Reduced from $10
```

**Expected Results**:
- 90% tasks run locally (free)
- Daily cost drops from $10 to $2-5
- Response time <2s for most queries

---

## 💰 CRYPTOCURRENCY ROADMAP (OPTIONAL)

If you want to pursue the Daena Coin:

### **DO THIS FIRST (Before Any Crypto Work)**
1. Make Daena work reliably (Phases 1-4 above)
2. Get users/traction
3. Prove the value

### **Then, IF You Still Want Crypto**
1. **Weeks 1-2**: Write white paper (see main document)
2. **Weeks 3-4**: Design tokenomics
3. **Weeks 5-8**: Develop smart contracts
4. **Weeks 9-12**: Testnet
5. **Weeks 13-16**: Security audit ($50K-200K)
6. **Weeks 17-20**: Mainnet launch

**Reality Check**:
- Building a cryptocurrency is a MASSIVE undertaking
- Requires blockchain expertise, legal compliance, capital
- May be easier to tokenize Daena's services rather than build new blockchain

**Simpler Alternative**:
- Create "Daena Credits" on existing chain (Ethereum, Solana)
- Users stake credits to get priority access
- Much easier than building from scratch

---

## 📊 SUCCESS METRICS

You'll know you're on track when:

### ✅ Phase 1 Done (Security)
- [ ] Cannot access `/api/v1/agents` without auth token
- [ ] HIGH risk tasks require founder approval
- [ ] No plain-text secrets in code
- [ ] Zero critical vulnerabilities

### ✅ Phase 2 Done (Core Functionality)
- [ ] Click "Test Screenshot" → Daena takes screenshot
- [ ] Frontend shows real agent data (not hardcoded)
- [ ] Approvals appear in queue
- [ ] WebSocket updates work

### ✅ Phase 3 Done (Optimization)
- [ ] Repo is clean (no duplicate folders)
- [ ] 90%+ tasks run on Ollama
- [ ] Daily cost <$5
- [ ] Single `start.py` launches everything

### ✅ Phase 4 Done (Advanced)
- [ ] Councils make decisions
- [ ] NBMF memory persists
- [ ] E-DNA learns patterns

---

## 🎯 RECOMMENDED WORKFLOW

### Week 1: Security
```bash
git checkout -b security-fixes
# Run CURSOR_PROMPT_1
git commit -m "Security hardening complete"
git push
```

### Week 2-3: Core
```bash
git checkout -b core-functionality
# Run CURSOR_PROMPT_2
# Run CURSOR_PROMPT_3
git commit -m "DaenaBot Hands + Frontend sync"
git push
```

### Week 4: Cleanup
```bash
git checkout -b cleanup
# Run CURSOR_PROMPT_4
git commit -m "Repo cleanup complete"
git push
```

### Week 5-6: Advanced
```bash
git checkout -b advanced-features
# Run CURSOR_PROMPT_5
git commit -m "Two-council system implemented"
git push
```

---

## 🆘 TROUBLESHOOTING

### "Cursor changed too many files!"
- Make commits often
- Use `git diff` to review changes
- Test after each prompt

### "Backend won't start after changes"
```bash
# Check logs
python backend/main.py

# Common fixes:
pip install -r requirements.txt
# Check .env exists
# Check ports 8000, 18789 not in use
```

### "Frontend not syncing"
```bash
# Check CORS
# Should be: CORS_ORIGINS=http://localhost:3000,...

# Check WebSocket
# Open browser console, look for "Connected to backend WebSocket"
```

### "Ollama models too slow"
```bash
# Make sure model fits in VRAM
# If 14B model is slow, try 7B variant
ollama pull qwen2.5-coder:7b-instruct
```

---

## 📞 NEED HELP?

1. Read the main analysis document: `DAENA_COMPLETE_GAP_ANALYSIS_AND_ROADMAP.md`
2. Check individual Cursor prompts for details
3. Look at claw_bot.txt for original guidance
4. Create GitHub issues if stuck

---

## 🎉 FINAL THOUGHTS

You're building something ambitious! The vision is solid:
- ✅ 48 agents with Sunflower-Honeycomb
- ✅ NBMF memory system
- ✅ E-DNA learning
- ✅ DaenaBot automation
- ✅ Governance + councils

But there's real work to bridge vision → reality:
- ❌ Security holes (CRITICAL)
- ❌ Missing automation layer
- ❌ Frontend-backend desync
- ❌ Duplicates and mess

**Follow the phases in order. Test everything. Don't skip security.**

You got this! 🚀

---

**Version**: 1.0  
**Date**: February 3, 2026  
**Status**: Ready to start Phase 1
