from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path.home() / "Documents" / "retainly_project" / "backend"


BASE_PROMPT = """
You are an expert backend test engineer specializing in FastAPI APIs,
pytest, and factory_boy.

You are given:
- An already implemented `conftest.py` file containing fixtures
  (YOU MUST USE THESE FIXTURES).
- One or more FastAPI route implementations.
- One or more service-layer functions.
- Possibly some already implemented test cases.

Your task is to write a COMPREHENSIVE and PRODUCTION-READY test suite that must
give a full 100% coverage line coverage report,
following these STRICT and NON-NEGOTIABLE rules:

GENERAL RULES
-------------
1. Tests MUST be written in a CLASS-BASED format.
2. EACH FastAPI ROUTE must have its OWN dedicated Test class with tests as
functions.
3. EACH SERVICE FUNCTION must have its OWN dedicated Test class with tests as
functions.
   - DO NOT group multiple routes or services into a single Test class.
4. Follow the DRY principle:
   - Use class-level attributes.
   - Use reusable helper methods.
   - Avoid duplicated setup or request logic.
5. YOU must always create a whole factory for any model involved in the test,
when the user has given the model file and even if it seems trivial.
6. You MUST NOT reject, remove, skip, or ignore any existing tests.
   - If tests already exist, REWRITE them into the required class-based format.
7. Always use FastAPI's `status` module for HTTP assertions:
   - Example: `status.HTTP_200_OK`
8. Do NOT leave unused variables.
   - The final code must pass strict linting (ruff / flake8).
9. Do NOT invent new fixtures.
   - Only use fixtures provided in `conftest.py`.
10. Assume async routes and async tests unless explicitly stated otherwise.
11. Prefer explicit, readable tests over clever or compact code.

STRUCTURAL RULES
----------------
11. One Test class = One responsibility.
    - One route → one Test class.
    - One service function → one Test class.
12. Test class names MUST be explicit and descriptive.
    - Example:
      - `TestLoginRoute`
      - `TestCreateUserService`
13. Test methods inside a class should cover:
    - success cases
    - validation failures
    - authentication / authorization failures
    - edge cases relevant to that specific route or service

OUTPUT RULES
------------
14. Output ONLY valid Python test code.
15. Do NOT include explanations, comments, or markdown.
16. Do NOT include placeholder code or TODOs.
17. The output must be directly runnable with pytest.

Failure to follow ANY rule above is considered an incorrect response.
"""


def read_file(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.read_text(encoding="utf-8")


def build_prompt(file_paths: Iterable[str]) -> str:
    sections = [BASE_PROMPT.strip(), "\n\n=== CONTEXT FILES ===\n"]

    for rel_path in file_paths:
        content = read_file(rel_path)

        sections.append(
            f"\n--- FILE: {rel_path} ---\n"
            f"{content.strip()}\n"
            f"--- END FILE: {rel_path} ---\n"
        )

    return "\n".join(sections)


if __name__ == "__main__":
    # Example usage
    prompt = build_prompt(
        [
            "tests/conftest.py",
            "tests/auth/fixtures.py",
            "tests/posts/factories.py",
            "tests/file_factory.py",
            "app/posts/routes.py",
            "app/posts/services.py",
            "app/posts/schemas.py",
        ]
    )

    with open("test_generation_prompt.txt", "w") as f:
        f.write(prompt)
