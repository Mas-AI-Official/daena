# Contributing to Daena

Thank you for your interest in contributing to Daena!

## How to Contribute

### Bug Reports
- Open a GitHub issue with: steps to reproduce, expected behavior, actual behavior, screenshots if applicable
- Include your OS, browser, Ollama version, and Daena version

### Feature Requests
- Open a GitHub issue with the "feature request" label
- Describe the use case, not just the solution

### Code Contributions
1. Fork the repository
2. Create a feature branch: `git checkout -b fix/your-fix-name`
3. Make your changes
4. Run tests: `pytest` (backend), `npm run build` (frontend)
5. Commit with clear messages: `fix: description` or `feat: description`
6. Open a Pull Request

### Priority Contribution Areas
- **Runtime Adapters**: Add support for new CLI tools or MCP servers
- **Governance Patterns**: New SecurityGate detection rules
- **Skills**: Submit skills to the catalog
- **Documentation**: Improve docs, add translations
- **Bug Fixes**: Check open issues labeled "good first issue"

## Development Setup

```bash
# Backend
cd daena
pip install -r requirements.txt
pip install -r requirements-dev.txt
python run.py

# Frontend
cd frontend
npm install
npm run dev

# Tests
pytest                  # Backend (1064 tests)
npx tsc --noEmit       # TypeScript check
npm run build           # Frontend build
```

## Code Style
- Backend: Python, PEP 8, type hints preferred
- Frontend: TypeScript, React functional components, Tailwind CSS
- No em dashes in any content

## License
By contributing, you agree that your contributions will be licensed under the BSL 1.1 license.
