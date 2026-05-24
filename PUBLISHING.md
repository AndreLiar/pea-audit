# Publishing `pea-audit` to PyPI

Maintainer-only. End users don't need any of this — `pip install pea-audit` already works.

PyPI publication uses [trusted publishers](https://docs.pypi.org/trusted-publishers/) (OIDC). No PyPI API token secret in CI; GitHub mints a short-lived OIDC token at deploy time and PyPI accepts it because the project is configured to trust this repo's `release.yml` workflow.

## One-time setup

1. **PyPI account.** Create at https://pypi.org/account/register/, enable 2FA (required for upload since 2024).
2. **Pending publisher.** Go to https://pypi.org/manage/account/publishing/ → *Add a new pending publisher*, fill:
   - PyPI Project Name: `pea-audit`
   - Owner: `AndreLiar`
   - Repository name: `pea-audit`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. **GitHub environment.** Repo Settings → Environments → New environment named `pypi`. Add `AndreLiar` as a required reviewer (deployments pause for explicit click-to-approve — critical because PyPI versions are immutable).

After the first successful publish, the pending publisher becomes a regular trusted publisher and the PyPI project is owned by `AndreLiar`.

## Per release

```bash
# 1. Bump version in pyproject.toml + add CHANGELOG.md entry.
#    (PyPI versions are immutable — bump even for one-char fixes.)

# 2. Verify locally.
python -m build              # produces dist/*.whl + *.tar.gz
pytest tests/                # 28/28
python evals/run.py          # 13/13 (costs 0 if cache warm)

# 3. Tag and push.
git tag v0.1.1
git push origin v0.1.1
```

The `release.yml` workflow:
1. Fires on tag push.
2. Enters the `pypi` environment → pauses for the required reviewer to click *Approve and deploy*.
3. Builds wheel + sdist.
4. `pypa/gh-action-pypi-publish` mints an OIDC token, uploads to PyPI.
5. Within ~30 seconds, `pip install pea-audit==<new-version>` works worldwide.

## Gotchas

- **The tag must match the version.** If `pyproject.toml` says `0.1.1`, tag `v0.1.1`. Mismatches don't break the workflow but look unprofessional and confuse `git describe`-style tooling.
- **README rendering.** PyPI uses GFM. Preview locally with `python -m readme_renderer README.md -o /tmp/r.html` if you've added unusual markdown.
- **Yanking a release.** If a version turns out to be broken, `pip` can be told to skip it — go to the project page on PyPI, click on the version, select "Yank". The wheel stays uploaded (you can never delete) but new installs skip it. Then publish a `.1` bump.
- **Trusted publisher mismatch.** If CI fails with "trusted publishing not configured", double-check the pending-publisher form values match the repo/workflow/environment names byte-for-byte.

## When something else breaks

- **Build fails on `python -m build`:** usually a missing file in `pyproject.toml`'s include/exclude lists. Add to `[tool.hatch.build] include = [...]` and re-test.
- **Wheel missing prompts:** the `build` job in `ci.yml` has a verification step that fails loudly if `pea_audit/prompts/*.md` aren't in the wheel. Re-run after fixing.
- **Tag pushed by mistake:** delete with `git tag -d v0.x.y && git push --delete origin v0.x.y`. If the workflow already published, you must bump to a new version — PyPI never lets you re-upload the same version.
