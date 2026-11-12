# Contributing

Thanks for helping improve GitHub Repository Inspector. Contributions should
keep repository inspection bounded, evidence-backed, and safe for untrusted
repository content.

## Before you start

- Check the README and open issues for existing plans or reports of the same
  problem.
- For a larger change, open an issue first so we can agree on scope.
- Do not include real API keys, `.env` files, private repository data, or
  generated credentials in a commit.

## Development setup

The API setup and Flutter client commands are in the README. For backend work,
install `api/requirements.txt` and run the existing suite from the repository
root:

```bash
PYTHONPATH=api pytest
```

## Pull requests

- Use a focused branch and explain the user-visible change or bug fix.
- Include or update tests when behavior changes.
- Keep GitHub API inspection bounded; do not clone or execute inspected code.
- Treat repository-derived text as untrusted input and do not send source code
  to the optional AI provider.
- Update the README when API behavior, configuration, or setup changes.
- Link the related issue and describe any manual verification performed.

The project is released under the MIT License. By submitting a contribution,
you agree that it may be distributed under that license.
