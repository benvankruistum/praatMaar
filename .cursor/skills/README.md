# Matt Pocock engineering skills

Vendored copy of selected skills from
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT — see `LICENSE`).

Cursor loads each `*/SKILL.md` as a project skill. Invoke with `/name`
(e.g. `/grill-with-docs`). Repo wiring for issue tracker / triage / domain docs:
`docs/agents/` and the `## Agent skills` block in `CLAUDE.md`.

To refresh from upstream:

```bash
npx skills@latest add mattpocock/skills
# or re-copy the desired folders from the upstream `skills/engineering/` tree
# into this directory, keeping LICENSE.
```
