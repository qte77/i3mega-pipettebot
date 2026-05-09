---
paths:
  - "tests/**/*.py"
---

# Testing Rules

- Mock external dependencies (HTTP, file systems, hardware serial APIs)
- Use pytest with arrange/act/assert structure
- Mirror `src/` and `tools/` structure in `tests/`
- Use `tmp_path` for filesystem isolation
- Tag hardware tests with `@pytest.mark.hardware` — excluded from `make test` by default
