# GitHub Copilot Instructions

Quick run
- Install dependencies: `pip install -r requirements.txt`
- Run via Python: `python main.py`
- Or use Uvicorn CLI: `uvicorn main:app --reload`

When suggesting code
- Keep changes minimal and focused; prefer small, testable commits.
- Follow existing style (PEP8); add type hints where practical.
- Do not introduce new dependencies without explicit approval; if needed, add them to `requirements.txt` and document the reason.
- Add or update tests when changing behavior; include simple examples for new endpoints.

Branching & commits
- Branch naming: `copilot/<short-description>`.
- Commit messages: present-tense, concise (e.g. "Add health endpoint").

Files to be careful with
- `main.py`: application entry (contains a uvicorn runner).
- `requirements.txt`: dependency manifest.

If you're unsure about an approach, suggest 2 alternatives and ask before changing the dependency list.

End of instructions.
