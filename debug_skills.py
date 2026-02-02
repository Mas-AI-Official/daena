import urllib.request
import json
import sys

try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/v1/skills') as r:
        data = json.load(r)
        skills = data.get('skills', [])
        print(f"Total skills returned: {len(skills)}")
        for s in skills:
            print(f"- {s.get('name')} | Category: {s.get('category')} | Source: {s.get('source', 'unknown')}")
except Exception as e:
    print(f"Error: {e}")
