# Demo playbook

This file is the **source of truth** for the hop README demo. It describes what
the demo shows; the other files in `demo/` are the "ingredients" that implement
it. If you change the storyline here, update the ingredients to match (see
[Updating the demo](#updating-the-demo)).

## Storyline

The demo records a real terminal, so it shows hop *and* the shell around it:

- Start in the synthetic repo with the terminal on the **`main`** branch.
- Show the current branch (`git branch --show-current` → `main`).
- Launch **`hop`**. `main` is the top row, so it starts selected.
- Press **`n`** to create a new branch from `main`; type **`feature/quick-fix`**; press **Enter** — hop creates the branch and checks it out.
- Press **`q`** to quit hop, back to the terminal (now on `feature/quick-fix`).
- Make a small commit in the terminal (append a line, `git add`, `git commit`).
- Launch **`hop`** again. The new branch is now the top row; `main` is one row below.
- Press **`j`** to move down to `main`, then **`c`** to check it out — back on the original branch.
- Press **`q`** to quit; the terminal is on `main` again.

## Ingredients

| File | Role |
| --- | --- |
| `PLAYBOOK.md` | This spec — the storyline above. |
| `make_repo.py` | Builds the deterministic synthetic repo (branches, upstream states, `main` on top, local git identity). |
| `demo.tape` | [VHS](https://github.com/charmbracelet/vhs) script that performs the storyline and renders `demo.gif`. |
| `demo.gif` | The generated recording, embedded in the top-level `README.md`. |

## Generating

Requires [`vhs`](https://github.com/charmbracelet/vhs) and `hop` on `PATH`
(`uv tool install .` from the repo root). From the repo root:

```bash
vhs demo/demo.tape        # builds the synthetic repo and writes demo/demo.gif
```

## Updating the demo

**For Claude / maintainers — keep the ingredients in sync with the storyline above.**

When the storyline changes, update the ingredients and re-validate:

1. **`make_repo.py`** — adjust if the storyline needs different branches or
   upstream states. Invariant the storyline depends on: **`main` sorts to the
   top row** (it is committed last with the newest date) and a **local git
   identity is configured** (so the demo's own `git commit` works).
2. **`demo.tape`** — mirror the storyline's steps as VHS commands. Keep the key
   presses aligned with hop's bindings: `n` new branch, `c` checkout, `j`/`k`
   or arrows to move, `q` quit. The branch-name input has no prefix in the
   synthetic repo, so type the full name.
3. **Validate the hop keystrokes headlessly** (no `vhs` needed) before
   recording — drive the app with Textual's `Pilot` against the synthetic repo
   and assert the branch state after each step, e.g.:

   ```python
   # build the repo with make_repo.build(...), os.chdir into it, then:
   #   press "n", type the name, press "enter"  -> current branch == new branch
   #   (commit in the shell)                    -> HEAD moved
   #   press "j" to reach main, press "c"        -> current branch == "main"
   ```

   This catches wrong key sequences or row counts that a silent GIF would hide.
4. **Regenerate** `demo.gif` with `vhs demo/demo.tape` and confirm it matches
   the storyline, then commit the updated `demo.gif`.
5. Keep this table of steps and the tape in the **same order**; the tape's
   comments reference these bullet points.
