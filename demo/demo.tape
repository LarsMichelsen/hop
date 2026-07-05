# hop demo — regenerate with:  vhs demo/demo.tape && uv run python demo/keycaps.py
# (needs `vhs`, `ttyd`, `ffmpeg` and `hop` on PATH). Run from the repository root.
#
# The storyline is specified in demo/PLAYBOOK.md; keep this tape in sync with it.
# vhs writes the base recording; demo/keycaps.py overlays the key-press badges.
# The Sleep budget below is deterministic on purpose so the badge timings in
# keycaps.py stay valid across re-renders — if you change a Sleep, re-measure.

Output demo/demo.gif

Require hop

Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 640
Set Padding 16
Set TypingSpeed 90ms

# Solarized Dark (canonical mapping — bright slots hold the base tones). hop's
# default "auto" theme adapts to these terminal colors.
Set Theme { "name": "Solarized Dark", "background": "#002b36", "foreground": "#839496", "cursor": "#839496", "selection": "#073642", "black": "#073642", "red": "#dc322f", "green": "#859900", "yellow": "#b58900", "blue": "#268bd2", "magenta": "#d33682", "cyan": "#2aa198", "white": "#eee8d5", "brightBlack": "#002b36", "brightRed": "#cb4b16", "brightGreen": "#586e75", "brightYellow": "#657b83", "brightBlue": "#839496", "brightMagenta": "#6c71c4", "brightCyan": "#93a1a1", "brightWhite": "#fdf6e3" }

# --- setup (hidden): isolated HOME, a prompt that shows the current branch, and
#     the synthetic repo; start on main -----------------------------------------
Hide
Type "export HOME=$(mktemp -d); export PROMPT_COMMAND='b=$(git branch --show-current 2>/dev/null)'; export PS1='demo ${b:+($b) }$ '; clear" Enter
Type "python3 demo/make_repo.py /tmp/hop-demo >/dev/null && cd /tmp/hop-demo && clear" Enter
# Stay hidden until make_repo finishes and its `clear` runs — otherwise Show
# reveals the still-running setup command before the screen clears. Hidden time
# is not recorded, so this does not lengthen the GIF.
Sleep 3s
Show

# the prompt already shows the branch — (main) — so no `git branch` needed
Sleep 1.5s

# launch hop; main is the top row, so it starts selected
Type "hop" Enter
Sleep 2s

# press n -> the "Create new branch from 'main'" dialog opens
Type "n"
Sleep 1.2s

# type the branch name
Type "feature/quick-fix"
Sleep 800ms

# Enter -> hop creates + checks out the branch; hold on the footer status
Enter
Sleep 2.5s

# quit hop; the prompt now reads (feature/quick-fix)
Type "q"
Sleep 2s

# make a small commit on the new branch
Type "echo 'tweak the footer layout' >> notes.md" Enter
Sleep 500ms
Type "git add notes.md && git commit -m 'Jot down a quick fix'" Enter
Sleep 2s

# launch hop again; feature/quick-fix is now the top row, main one row below
Type "hop" Enter
Sleep 2s

# press Down to move the cursor from feature/quick-fix to main
Down
Sleep 1.2s

# press c to check out main; hold on the "Checked out branch: main" status
Type "c"
Sleep 2.5s

# quit; the prompt reads (main) again
Type "q"
Sleep 2s
