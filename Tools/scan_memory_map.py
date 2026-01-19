import os, re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # ./Daena
EXCLUDE = {"node_modules", ".venv", ".git", "__pycache__", "dist", "build", ".idea", ".vscode"}
EXTS = {".py", ".ts", ".js", ".tsx", ".json", ".yaml", ".yml"}

PATTERNS = {
    "read_write": re.compile(r"\b(read|write|save|load|persist|recall|store|cache)\b", re.I),
    "vector_rag": re.compile(r"\b(embedding|vector|faiss|milvus|weaviate|chroma|rag)\b", re.I),
    "db": re.compile(r"\b(sqlite|postgres|mongodb|redis|table|collection)\b", re.I),
    "llm": re.compile(r"\b(openai|anthropic|gpt|claude|gemini|deepseek|grok|xai)\b", re.I),
    "emotion": re.compile(r"\b(emotion|sentiment|tone|valence|arousal|affect|personality)\b", re.I),
}

def scan(path):
    try:
        if path.suffix not in EXTS:
            return None
        text = path.read_text(errors="ignore")
    except: 
        return None
    
    hits = {k: bool(rx.search(text)) for k, rx in PATTERNS.items()}
    if not any(hits.values()):
        return None
    
    return {
        "path": str(path.relative_to(ROOT)),
        "hits": hits
    }

def main():
    results = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for f in files:
            p = Path(root) / f
            r = scan(p)
            if r: results.append(r)

    graph = [
        "Agent → CMP Router → LLM APIs → Memory Write (cache/raw/log)",
        "Agent ← Memory Recall ← Embeddings / Logs / Summaries",
        "UI/Voice → Backend API → Memory → Agent"
    ]

    print(json.dumps({
        "root": str(ROOT),
        "flagged_files": len(results),
        "impact_map": results,
        "data_flow": graph,
        "footer": "✅ MEMORY MAP COMPLETE — READY FOR PHASE 2"
    }, indent=2))

if __name__ == "__main__":
    main()
