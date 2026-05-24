<!-- Thanks for contributing! Please confirm the checks below. -->

## What does this PR do?

<!-- Short description. If it adds a KIDSource or VisionLLM, name the issuer/provider. -->

## Type of change

- [ ] Bug fix
- [ ] New `KIDSource` (issuer / ticker)
- [ ] New `VisionLLM` backend
- [ ] New eval case
- [ ] Prompt change (note: requires version bump + cache bust + eval re-run)
- [ ] Docs / examples
- [ ] CI / packaging
- [ ] Other (describe above)

## Checklist

- [ ] `pytest tests/ -v` passes locally
- [ ] `python evals/run.py` passes (or you've explained why a case must change)
- [ ] If you added a public function/class, included a docstring with at least one usage example
- [ ] If you added a dependency, declared it in `pyproject.toml` under the right extras group
- [ ] Updated `CHANGELOG.md` under the unreleased / next-version heading

<!-- For prompt changes: paste the eval baseline output before + after the change. -->
