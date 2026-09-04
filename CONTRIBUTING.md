# Contributing

Thanks for your interest in contributing to the AI-Assisted Development Methodology!

## Ways to Contribute

- **Report issues**: Found a bug in a fitness check script? Template not rendering correctly? Open an issue.
- **Propose enhancements**: Have an idea for a new quality dimension, a better agent workflow, or a missing template? Open a feature request.
- **Add examples**: Share how you adapted the methodology to your stack by contributing to `examples/`.
- **Improve translations**: Help translate core documents into additional languages under `i18n/`.
- **Fix bugs**: Pick up an open issue and submit a PR.

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Make your changes. Keep them focused — one concern per PR.
3. If you're adding or modifying a fitness check script, include a test.
4. Run `python3 scripts/onboard.py --plan --json` and, for an existing integration, `python3 scripts/onboard.py --check` to verify nothing is broken.
5. Update `CHANGELOG.md` under the `[Unreleased]` section.
6. Open a PR with a clear description of what changed and why.

## Language Policy

- **English** is the authoritative language for `core/` documents.
- **Translations** live under `i18n/<lang>/core/` and should mirror the English source.
- Templates (`templates/`) use `{{PLACEHOLDER}}` syntax and are language-neutral.
- Discussion in issues and PRs can be in any language, but English is preferred for searchability.

## Code of Conduct

- Be respectful and constructive.
- Assume good intent.
- Focus on the methodology, not the person.

## Development

```bash
# Preview onboarding changes (read-only)
python3 scripts/onboard.py --plan --json
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
