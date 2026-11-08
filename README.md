# ctxfill

**Automatic handoff for Claude Code: when a session's context window reaches X %, it wraps itself up.
Set it up once; every session on your machine follows it from then on.**

Handoff is the usual choice. The action is yours to define: commit and stop, compact, write a
handoff file and tell you, post a status line, anything Claude can be told to do.

```
$ ctxfill
596bf40d  claude-fable-5-1       260,094 tokens   26.0% of 1,000,000  last turn 2026-11-08 22:37 CET
```

One Python file, no dependencies, macOS / Linux / WSL. Claude Code in the terminal or the desktop app.

## Why this exists

From the author:

> I am a Claude Code desktop user only. I have had to micro-babysit every session and manually hand it
> off when I judged the context window was getting full. Claude told me it cannot sense its own context
> usage, and when it tried anyway it was always wrong.
>
> My Fable systems-engineer session found another way and made this tool. Now actions can finally be
> customized on context usage, and I can stop babysitting and let the windows run themselves.

The first session asked to test it guessed "about 40 %" of its window before running it. The tool read 58.9 %.

## Set it up once, with Claude

You do not need to edit anything by hand. Open any Claude Code session and paste this, filling the brackets:

> Install ctxfill from https://github.com/zheng2026/ctxfill and add a Stop hook to my global Claude Code
> settings so that whenever ANY session's context window reaches [75] %, Claude [writes a handoff file
> for the next session and tells me / commits what works and stops / your own action]. My context window
> is [1M / 200k]. Show me the hook before you save it, then test it on this session.

Claude will clone the repo, write the hook into `~/.claude/settings.json`, show it to you, and run a check.
From the next turn on, every session you open follows it. You never tell a session anything; the hook is
there before the session starts. Change the threshold or the action later by pasting a new sentence.

## What you get

Below the threshold: nothing changes, sessions stop and start as usual.

At the threshold, the next time the session tries to stop, Claude is instead handed your instruction with
the live number in it, for example:

> Context window is at 82.3% (823,105 of 1,000,000 tokens). Wrap up now: save state to disk and run the close ceremony.

It then does that, and stops. No babysitting, no guessing, same behaviour in every window.

## Set it up by hand

If you would rather see the pieces:

```sh
git clone https://github.com/zheng2026/ctxfill.git
ln -s "$PWD/ctxfill/ctxfill.py" ~/.local/bin/ctxfill   # or anywhere on your PATH
```

Then in `~/.claude/settings.json` (the global file, so it covers every session):

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "ctxfill --hook --stop-at 80" } ] }
    ]
  }
}
```

Your own action goes in `--reason` (placeholders `{percent}`, `{tokens}`, `{window}`):

```sh
ctxfill --hook --stop-at 75 --reason "Context at {percent}%. Write HANDOFF.md for the next session, tell Jade, then stop."
ctxfill --hook --stop-at 70 --reason "Context at {percent}%. Commit what works, then stop."
ctxfill --hook --stop-at 90 --reason "Context at {percent}%. Run /compact now."
```

Two thresholds, two actions: two command entries in the same hook. A hook must never break a session,
so on any unreadable input ctxfill prints nothing and exits 0.

**Window size.** ctxfill assumes 1,000,000 tokens, which most Claude Code plans have today, and prints a
reminder on every interactive run until you set yours. If your plan differs, add it to the hook command
(`--200k` or `--window N`) or put `export CTXFILL_WINDOW=200000` in your shell profile. The transcript does
not record the window size, so ctxfill cannot detect it; a figure above 100 % means the assumed window is wrong.

## How it works

A Claude Code session cannot sense its own context. Nothing in the conversation tells the model how many
tokens it carries. The usage ring under the prompt box is *plan* usage, not the window. `/context` prints a
breakdown, but only for a human at the keyboard.

Yet the number is on disk. Claude Code appends every turn to the session's transcript:

```
~/.claude/projects/<folder-slug>/<session-id>.jsonl
```

Each assistant record carries a `usage` block, and the context the next turn will carry is exactly

```
input_tokens + cache_read_input_tokens + cache_creation_input_tokens
```

of the **last** such record. ctxfill reads that record and prints the sum. Claude Code hands every hook
the session's `transcript_path` on stdin, so a Stop hook can read its own session's number precisely.

## Read the number yourself

```sh
ctxfill                      # newest session of the current folder
ctxfill <session-id>         # one session, found anywhere under ~/.claude/projects
ctxfill <transcript.jsonl>   # one file
ctxfill <folder>             # newest session of that project folder
ctxfill --all                # every session of this folder, by last turn, compactions flagged
ctxfill --json               # machine-readable
ctxfill -q                   # without the window reminder
```

Other uses of the same number:

- **Status line.** The status-line command also gets `transcript_path` on stdin: `ctxfill --hook -q`.
- **Log every turn.** A Stop hook without `--stop-at`: `ctxfill --hook >> ~/.claude/ctxfill.log`.
- **A coordinator watching its workers.** `ctxfill --all <folder>` from another session. This is how
  the number was first measured: three live sessions read from a fourth, 399k / 561k / 581k of 1M,
  none compacted, while each had been calling itself "a lot".

## Caveats

- The window size is not in the transcript. Default 1M; set `CTXFILL_WINDOW` or pass `--window`/`--200k`.
- The newest transcript in a folder is a heuristic for "the current session". Hooks get the exact path.
- A session does not know its own session id, so from inside a session use the folder form or a hook.
- In the Claude desktop app, a session's link carries an app id (`local_…`) that is **not** the transcript's
  id; `ctxfill <that-id>` finds nothing. Use the folder form or `--all` and match by model and last-turn time.
- Subagent transcripts live beside the parent's and are counted as sessions by `--all`.
- Tested with Claude Code transcripts of November 2026. The record format is Anthropic's and may change.

## Credit

Found and measured on 2026-11-05 by Jade Zheng together with Claude (Fable 5.1) inside Claude Code,
when a window was asked how full it was and could not say. Built as a tool on 2026-11-08, the same way.
MIT licence.
