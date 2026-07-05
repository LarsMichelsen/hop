# Demo playbook

This file is the **source of truth** for the hop README demo. It describes what
the demo shows; the other files in `demo/` are the "ingredients" that implement
it. If you change the storyline here, update the ingredients to match (see
[Updating the demo](#updating-the-demo)).

## Storyline

The demo records a real terminal, so it shows hop *and* the shell around it. Two
conventions make it legible:

- **The shell prompt shows the current branch** — `demo (main) $` — so branch
  switches are visible in the terminal without running `git branch`.
- **hop's key presses have no on-screen echo**, so each one is shown as a small
  on-screen badge naming the key and its action (e.g. `n  new branch`).

Steps:

- Start in the synthetic repo; the prompt shows the terminal is on **`main`**.
- Launch **`hop`**. `main` is the top row, so it starts selected.
- Press **`n`** to create a new branch from `main`; type **`feature/quick-fix`**; press **Enter** — hop creates and checks it out (footer: "Created and checked out branch: …").
- Press **`q`** to quit hop; the prompt now reads `demo (feature/quick-fix) $`.
- Make a small commit in the terminal (append a line, `git add`, `git commit`).
- Launch **`hop`** again. The new branch is now the top row; `main` is one row below.
- Press **`↓`** to move down to `main`, then **`c`** to check it out (footer: "Checked out branch: main").
- Press **`q`** to quit; the prompt reads `demo (main) $` again.

## Ingredients

| File | Role |
| --- | --- |
| `PLAYBOOK.md` | This spec — the storyline above. |
| `make_repo.py` | Builds the deterministic synthetic repo (branches, upstream states, `main` on top, local git identity). |
| `demo.tape` | [VHS](https://github.com/charmbracelet/vhs) script that sets up the branch-showing prompt, performs the storyline, and renders the base `demo.gif`. |
| `keycaps.py` | Overlays the key-press badges onto the base `demo.gif` with `ffmpeg` (VHS has no keycast of its own), and disables looping so the GIF freezes on the final frame. |
| `demo.gif` | The generated recording, embedded in the top-level `README.md`. |

## Generating

Requires `hop` on `PATH` (`uv tool install .` from the repo root) plus the VHS
toolchain: [`vhs`](https://github.com/charmbracelet/vhs) and the two tools it
shells out to — [`ttyd`](https://github.com/tsl0922/ttyd) and `ffmpeg`. From the
repo root:

```bash
vhs demo/demo.tape              # builds the synthetic repo, writes the base demo/demo.gif
uv run python demo/keycaps.py   # overlays the key-press badges onto demo/demo.gif in place
```

VHS records inside a headless Chromium. On kernels that restrict unprivileged
user namespaces (common on hardened / OEM setups — the symptom is
`sys_chroot(...)` / `ptrace: Operation not permitted` followed by `recording
failed`), Chromium's own sandbox can't start. Work around it by putting a
wrapper named `google-chrome` (or `chromium`) earlier on `PATH` that appends
`--no-sandbox`; VHS finds the browser via `PATH`, so the wrapper is picked up
transparently:

```bash
#!/bin/sh
exec /path/to/real/google-chrome --no-sandbox --disable-gpu --disable-dev-shm-usage "$@"
```

## Updating the demo

**For Claude / maintainers — keep the ingredients in sync with the storyline above.**

When the storyline changes, update the ingredients and re-validate:

1. **`make_repo.py`** — adjust if the storyline needs different branches or
   upstream states. Invariant the storyline depends on: **`main` sorts to the
   top row** (it is committed last with the newest date) and a **local git
   identity is configured** (so the demo's own `git commit` works).
2. **`demo.tape`** — mirror the storyline's steps as VHS commands. Keep the key
   presses aligned with hop's bindings: `n` new branch, `c` checkout, `Down`/`j`
   to move, `q` quit. The branch-name input has no prefix in the synthetic repo,
   so type the full name. Two invariants:
   - The branch-showing prompt is set in the hidden setup via `PROMPT_COMMAND`
     (recomputes the branch each prompt) and `PS1` (`demo ${b:+($b) }$`).
   - **Stay `Hide`den until make_repo finishes and its `clear` runs**, then
     `Show`. Otherwise `Show` reveals the still-running setup command before the
     screen clears. Hidden time is not recorded, so a generous `Sleep` is free.
   - Keep the visible **`Sleep` budget deterministic** — the badge timings in
     `keycaps.py` are measured against it.
3. **`keycaps.py`** — one badge per hop key press, each a `(label, start, end)`
   window in seconds. If you change a `Sleep` in `demo.tape`, re-measure the
   windows against the base GIF (build a timestamped contact sheet, e.g.
   `ffmpeg -i demo/demo.gif -vf "fps=2,drawtext=text='%{pts\:hms}':x=6:y=6:fontcolor=yellow:box=1,scale=360:-1,tile=6x10" sheet.png`)
   and update the `BADGES` list.
4. **Validate the hop keystrokes headlessly** (no `vhs` needed) before
   recording — drive the app with Textual's `Pilot` against the synthetic repo
   and assert the branch state after each step, e.g.:

   ```python
   # build the repo with make_repo.build(...), os.chdir into it, then:
   #   press "n", type the name, press "enter"  -> current branch == new branch
   #   (commit in the shell)                    -> HEAD moved
   #   press "down" to reach main, press "c"     -> current branch == "main"
   ```

   This catches wrong key sequences or row counts that a silent GIF would hide.
5. **Regenerate** `demo.gif`: `vhs demo/demo.tape && uv run python demo/keycaps.py`,
   then confirm it matches the storyline. To eyeball it without opening the GIF,
   extract frames: `ffmpeg -i demo/demo.gif -vf fps=1/2.2 frame%02d.png`. Then
   commit the updated `demo.gif` — it is tracked and embedded in the top-level
   `README.md`.
6. Keep this table of steps and the tape in the **same order**; the tape's
   comments reference these bullet points.
