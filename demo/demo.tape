# hop demo — regenerate with:  vhs demo/demo.tape   (needs `vhs` and `hop` on PATH)
#
# The storyline is specified in demo/PLAYBOOK.md; keep this tape in sync with it.
# Run from the repository root.

Output demo/demo.gif

Require hop

Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 640
Set Padding 16
Set TypingSpeed 90ms

# --- setup (hidden): isolated HOME + clean prompt, build the synthetic repo,
#     start on main ------------------------------------------------------------
Hide
Type "export HOME=$(mktemp -d); export PS1='demo$ '; clear" Enter
Type "python3 demo/make_repo.py /tmp/hop-demo >/dev/null && cd /tmp/hop-demo && clear" Enter
Show

# terminal is on main
Type "git branch --show-current" Enter
Sleep 1.2s

# launch hop and create a new branch off main (the top row), then check it out
Type "hop" Enter
Sleep 2s
Type "n"
Sleep 1s
Type "feature/quick-fix"
Sleep 800ms
Enter
Sleep 2s
Type "q"
Sleep 1.2s

# back in the terminal on feature/quick-fix — make a small commit
Type "echo 'tweak the footer layout' >> notes.md" Enter
Sleep 500ms
Type "git add notes.md && git commit -m 'Jot down a quick fix'" Enter
Sleep 2s

# launch hop again and hop back to main (now one row down)
Type "hop" Enter
Sleep 2s
Down
Sleep 800ms
Type "c"
Sleep 2s
Type "q"
Sleep 1.2s

# terminal is back on main
Type "git branch --show-current" Enter
Sleep 2s
