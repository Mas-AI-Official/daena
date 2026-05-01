name: predict-build-vs-buy
description: |
  Build vs. buy / pick-among-options decision support. Hands the question +
  N candidate options to Predictor /simulate; ranks them with persona
  reactions and 3-scenario probability distributions.

domain: build
tier_default: B
horizon_hours: 720         # 30 days; bump for longer-tail decisions

prompt_template: |
  We are deciding: {question}

  Candidate options:
  {options_bulleted}

  Constraints / context:
  {context}

evidence_adapters:
  - idea_reality
  - github_search
  - hn_search
  - product_hunt
  - scraper

personas: build           # uses BUILD_VS_BUY from src/predictor/simulation/personas.py

mirror_to_daena: true     # SKILLS SYNC RULE — mirror to D:\Ideas\Daena\skills\

example_inputs:
  - question: "Should we build a custom evidence-grading service or buy LangChain?"
    options:
      - "Build custom from scratch (3 engineer-months)"
      - "Adopt LangChain + customize"
      - "Use Haystack (more focused)"
      - "Defer; ship without it"

  - question: "Which prediction-market data feed for our trading R&D?"
    options:
      - "Polymarket API direct"
      - "Kalshi API direct"
      - "Aggregator (PMXT.dev)"
