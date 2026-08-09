---
name: verify
description: Drive the real hop TUI headlessly to verify changes at the terminal surface
---

# Verifying hop changes at the TUI surface

hop is a Textual TUI. tmux is not installed on this machine; drive the real
`hop` process in a pty and render its ANSI output with `pyte` instead.

## Recipe

1. Build a scratch repo in the session scratchpad with a known branch
   topology (`git init -b main`, `--allow-empty` commits, branches). Never
   run hop against a real repo when probing rebase/delete.
2. Write a driver script that:
   - opens a pty (`pty.openpty()`), sets the window size via
     `fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))`
   - spawns `["uv", "run", "--project", "/home/lm/git/hop", "hop"]` with
     `stdin/stdout/stderr=slave`, `cwd=<scratch repo>`, `TERM=xterm-256color`
   - pumps `os.read(master, ...)` into `pyte.ByteStream(pyte.Screen(...))`
     with a `select` loop, writes keys with `os.write(master, ...)`,
     and prints `screen.display` to capture frames
3. Run it with `uv run --project /home/lm/git/hop --with pyte python driver.py <repo>`.
4. Allow ~6-8s after launch: startup plus async per-branch metadata load.

## Gotchas

- The help screen (`h`) gives initial focus to its scroll container, not the
  Close button: plain Enter does nothing and `q` is swallowed by the modal.
  Close it with `\t` then `\r`. Scroll it with arrow keys (`\x1b[B`) or
  PageDown (`\x1b[6~`).
- Keys: arrows are `\x1b[A`/`\x1b[B`; `j`/`k` also navigate the branch list.
- If the driver dies mid-run the hop process lingers; `pkill -f "hop$"`.
- An editable uv-tool install of hop exists on PATH, but `uv run --project`
  is what guarantees the working tree is what runs.
