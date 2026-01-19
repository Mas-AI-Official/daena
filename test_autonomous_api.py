"""Test autonomous execution via API"""
import httpx
import json

url = "http://127.0.0.1:8000/api/v1/autonomous/execute"

payload = {
    "title": "Investor Landing Page for MAS-AI",
    "goal": "Create a landing page and investor materials for MAS-AI/Daena",
    "constraints": [
        "Must use verified internal data only",
        "No unverified market claims"
    ],
    "acceptance_criteria": [
        "Dashboard shows project created",
        "Deliverables in UI"
    ],
    "deliverables": [
        "Landing page HTML draft",
        "Investor cold email",
        "List of 6 confirmed capabilities",
        "Compliance notes"
    ]
}

try:
    response = httpx.post(url, json=payload, timeout=120.0)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
