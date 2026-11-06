# BugWarrior Service OpenProject

Provides an OpenProject Service task fetch for BugWarrior

This is stil an on-working project not intendeed for general public, anyway, feel free to test it and report any issue.

# Development

```
  python3 -m build && pipx inject bugwarrior dist/bugwarrior_service_openproject-1.0.1-py3-none-any.whl
```

The module is installed as `bugwarrior/services/openproject.py`, next to bugwarrior's own services. It must be injected into the same pipx environment as bugwarrior.

# Setup

vi ~/.config/bugwarrior/bugwarriorrc

# Run

bugwarrior-pull
