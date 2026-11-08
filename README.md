# ctxfill

**"When my Claude Code session's context window hits X %, do ___."**
This is the missing piece that makes that sentence possible: a reliable read of how full the window is, from the one place it is recorded.

```
$ ctxfill
596bf40d  claude-fable-5-1       260,094 tokens   26.0% of 1,000,000  last turn 2026-11-08 22:37
```

One Python file, no dependencies, macOS / Linux / WSL. Works for Claude Code in the terminal and in the desktop app.

## Why this exists

From the author:

> I am a Claude Code desktop user only. I have had to micro-babysit every session and manually hand it off when I judged the context window was getting full. Claude told me it cannot sense its own context usage, and when it tried anyway it was always wrong.
>
> My Fable systems-engineer session found another way and made this tool. Now actions can finally be customized on context usage, and I can stop babysitting and let the windows run themselves.

## The fact underneath

A Claude Code session cannot sense its own context. Nothing in the conversation tells the model how
many tokens it carries, so asked "how full are you?" it guesses, and guesses badly: one session said
"a lot" at 40 % and again at 56 %. The usage ring under the prompt box is *plan* usage, not the window.
`/context` prints a breakdown, but only for a human at the keyboard.

Yet the number is on disk. Claude Code appends every turn to the session's transcript:

```
~/.claude/projects/<folder-slug>/<session-id>.jsonl
```

Each assistant record carries a `usage` block, and the context the next turn will carry is exactly

```
input_tokens + cache_read_input_tokens + cache_creation_input_tokens
```

of the **last** such record. ctxfill finds the transcript, reads that record, prints the sum. That is all.
Everything else in this README is what you can build on top of a number you can trust.

## Install

```sh
git clone https://github.com/zheng2026/ctxfill.git
ln -s "$PWD/ctxfill/ctxfill.py" ~/.local/bin/ctxfill   # or anywhere on your PATH
```

Python 3.8+ only.

**Window size.** ctxfill assumes a 1,000,000-token window, which most Claude Code plans have today,
and says so on every run until you tell it otherwise. If your plan is different:

```sh
ctxfill --200k                       # once
export CTXFILL_WINDOW=200000         # for good, in ~/.zshrc or ~/.bashrc
ctxfill --window 500000              # any size
```

The transcript does not record the window size, so ctxfill cannot detect it. If a figure comes out
above 100 %, the assumed window is wrong, and the line tells you so.

## Read the number

```sh
ctxfill                      # newest session of the current folder
ctxfill <session-id>         # one session, found anywhere under ~/.claude/projects
ctxfill <transcript.jsonl>   # one file
ctxfill <folder>             # newest session of that project folder
ctxfill --all                # every session of this folder, newest first, with compactions flagged
ctxfill --json               # same, machine-readable
ctxfill -q                   # without the window reminder
```

Several sessions can share one folder. With no argument ctxfill picks the most recently written
transcript and says so; pass a session id or `--all` to choose.

## "When the window hits X %, do ___"

This is the part to customize. Claude Code hands every hook a JSON object on stdin that includes
`transcript_path`; `--hook` reads it. A `Stop` hook that prints `{"decision": "block", "reason": "..."}`
makes Claude keep working instead of stopping, with the reason as its next instruction. So:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "ctxfill --hook --stop-at 80" } ] }
    ]
  }
}
```

in `~/.claude/settings.json` means: below 80 % nothing happens; at 80 % or above, every time the
session tries to stop, Claude is told:

> Context window is at 82.3% (823,105 of 1,000,000 tokens). Wrap up now: save state to disk and run the close ceremony.

**The action is yours.** Handoff is what most people want, but the text is just a sentence Claude will
follow. Replace it with `--reason "..."` (placeholders `{percent}`, `{tokens}`, `{window}`):

```sh
ctxfill --hook --stop-at 70 --reason "Context at {percent}%. Commit what works, write HANDOFF.md, then stop."
ctxfill --hook --stop-at 90 --reason "Context at {percent}%. Run /compact now."
ctxfill --hook --stop-at 60 --reason "Context at {percent}%. Post a one-line status to the team channel before continuing."
```

Two thresholds, two actions: add two command entries to the same hook. A hook must never break a
session, so on any unreadable input ctxfill prints nothing and exits 0.

### Let Claude set it up for you

You do not have to edit JSON by hand. Open any Claude Code session and paste:

> Install ctxfill from https://github.com/zheng2026/ctxfill and add a Stop hook to my settings so that
> when a session's context window reaches 75 %, Claude [write a handoff file and tell me / commit and
> stop / your own action]. My context window is [1M / 200k]. Show me the hook before you save it.

Claude will ask what you want to happen and wire it. Change your mind later the same way.

### Other places the number is useful

- **Status line.** The status-line command also receives JSON on stdin with `transcript_path`, so
  `ctxfill --hook -q` works there too. (Recent Claude Code builds also pass
  `context_window.used_percentage` to the status line directly; ctxfill is for everywhere else.)
- **Log every turn.** A `Stop` hook without `--stop-at`: `ctxfill --hook >> ~/.claude/ctxfill.log`.
- **A coordinator watching its workers.** `ctxfill <session-id>` or `ctxfill --all <folder>` from another
  session. This is how the number was first measured: three live sessions read from a fourth,
  399k / 561k / 581k of 1M, none compacted, while each had been calling itself "a lot".

## Caveats

- The window size is not in the transcript. Default 1M; set `CTXFILL_WINDOW` or pass `--window`/`--200k`.
- The newest transcript in a folder is a heuristic for "the current session". Hooks and status lines
  get the exact path and should use `--hook`.
- A session does not know its own session id, so from inside a session use the folder form or a hook.
- In the Claude desktop app, a session's link carries an app id (`local_…`) that is **not** the transcript's
  id; `ctxfill <that-id>` finds nothing. Use the folder form or `--all` and match by model and last-turn time.
- Subagent transcripts live beside the parent's and are counted as sessions by `--all`.
- Tested with Claude Code transcripts of November 2026. The record format is Anthropic's and may change.

## Credit

Found and measured on 2026-11-05 by Jade Zheng together with Claude (Fable 5.1) inside Claude Code,
when a window was asked how full it was and could not say. Built as a tool on 2026-11-08, the same way.
MIT licence.
