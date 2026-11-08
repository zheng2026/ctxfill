# ctxfill

**How full is a Claude Code session's context window? The number is on disk. This reads it.**

```
$ ctxfill --1m
596bf40d  claude-fable-5-1       248,990 tokens   24.9% of 1,000,000  last turn 2026-11-08 22:28
```

One Python file, no dependencies, macOS / Linux / WSL.

## The problem

A Claude Code session cannot sense its own context window. Nothing in the conversation tells the
model how many tokens it is carrying, so when you ask "how much context have you used?" it guesses,
and it guesses badly: the same session once answered "a lot" at 40 % and again at 56 %.

The usage ring under the prompt box is your *plan* usage, not the context window. `/context` prints
a breakdown, but only for a human at the keyboard. The status line can receive a percentage, but
hooks and other sessions cannot. So the one number that decides when a long session should wrap up
is invisible to every piece of automation around it.

## The fact

Claude Code appends every turn to the session's transcript:

```
~/.claude/projects/<folder-slug>/<session-id>.jsonl
```

Each assistant record carries a `usage` block. The context the next turn will carry is exactly

```
input_tokens + cache_read_input_tokens + cache_creation_input_tokens
```

of the **last** assistant record. That is all ctxfill does: find the transcript, read the last
usage record, print the sum. For humans, for scripts, for status lines, for hooks.

## Install

```sh
git clone https://github.com/zheng2026/ctxfill.git
ln -s "$PWD/ctxfill/ctxfill.py" ~/.local/bin/ctxfill   # or anywhere on your PATH
```

Python 3.8+ only. If your plan has a 1M window, put `export CTXFILL_WINDOW=1000000` in your shell
profile (or pass `--1m` each time); the default assumes 200,000. The transcript does not record the
window size, so ctxfill cannot detect it.

## Use

```sh
ctxfill                      # newest session of the current folder
ctxfill <session-id>         # one session, found anywhere under ~/.claude/projects
ctxfill <transcript.jsonl>   # one file
ctxfill <folder>             # newest session of that project folder
ctxfill --all                # every session of this folder, newest first
ctxfill --json               # same, machine-readable
```

Several sessions can share one folder. With no argument ctxfill picks the most recently written
transcript and says so on stderr; pass a session id or `--all` to choose.

`--all` also flags compactions: a turn whose context is less than half the previous turn's.

## From a hook

Claude Code hands every hook a JSON object on stdin that includes `transcript_path`. `--hook` reads it.

**Force a clean close before the window fills.** A `Stop` hook that prints
`{"decision": "block", "reason": "..."}` makes Claude continue instead of stopping, with the reason
as its next instruction. In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "ctxfill --hook --1m --stop-at 80" }
        ]
      }
    ]
  }
}
```

Below 80 % it prints nothing and the session stops as usual. At 80 % or above, Claude is told:

> Context window is at 82.3% (823,105 of 1,000,000 tokens). Wrap up now: save state to disk and run the close ceremony.

Change the text with `--reason "..."` (placeholders `{percent}`, `{tokens}`, `{window}`).
A hook must never break a session, so on any unreadable input ctxfill prints nothing and exits 0.

**Log the number on every turn** (a `Stop` hook without `--stop-at`):

```json
{ "type": "command", "command": "ctxfill --hook --1m >> ~/.claude/ctxfill.log" }
```

## From the status line

Your status-line command also receives JSON on stdin with `transcript_path`, so the same flag works:

```sh
ctxfill --hook --1m
```

(Recent Claude Code builds also pass `context_window.used_percentage` to the status line directly.
ctxfill is for everywhere else that number does not reach.)

## From another session

A session that needs to know about another one, a coordinator checking its workers for example, can
call `ctxfill <session-id>` or `ctxfill --all <folder>`. This is how the number was first measured:
three live sessions read from a fourth, 399k / 561k / 581k of 1M, none compacted, while each of the
three had been describing itself as "a lot".

## Caveats

- The window size is not in the transcript. Set `CTXFILL_WINDOW` or pass `--window`/`--1m`.
- The newest transcript in a folder is a heuristic for "the current session". Hooks and status lines
  get the exact path and should use `--hook`.
- A session does not know its own session id, so from inside a session use the folder form or a hook.
- Subagent transcripts live beside the parent's and are counted as sessions by `--all`.
- Tested with Claude Code transcripts of November 2026. The record format is Anthropic's and may change.

## Credit

Found and measured on 2026-11-05 by Jade Zheng together with Claude (Fable 5.1) inside Claude Code,
when a window was asked how full it was and could not say. Built as a tool on 2026-11-08, the same
way. MIT licence.
