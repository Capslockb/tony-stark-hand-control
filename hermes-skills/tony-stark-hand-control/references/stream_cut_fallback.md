# Stream-Cut Fallback (large `write_file` in this environment)

## The pitfall

In this Hermes/Windows environment, two failure modes bite on large single-file rewrites of `tony_stark_hud_control.py` (>600 lines):

1. **Parent `write_file` cut off mid-stream.** A `write_file` carrying the full rewritten script gets interrupted by network errors, leaving a partial file on disk.
2. **Subagent `delegate_task` times out at 600s.** Even when a subagent is given a self-contained context and a single big `write_file` to do, the task is not guaranteed to finish in 600s. Observed in this session: 2 consecutive subagent attempts timed out with `status=timeout, exit_reason=timeout, api_calls=4-5, duration_seconds=600.0+`. No progress on disk.

Both end in the same place: the file is unchanged, the response stream is dead, and the user keeps re-asking for "the next concrete step" with no new information.

## How to recognize you're in the loop

- You start the same rewrite three or more times.
- Each time the response stream is cut off before the `write_file` returns, or the subagent reports `timeout`.
- The user keeps restating the original goal ("Continue working toward this goal...") without giving new information.
- You find yourself about to say "next concrete step" again with no real action behind it.

## The user-feedback signal you missed

The user's response to the loop is **"stop restating the goal in your reply"**. They were not asking for the work to be redone; they were asking for a different kind of answer. When you find yourself restating the same goal three or more times in a row without actually doing new work, that is the signal. The fix is to **explicitly say "I am blocked by [cause]" and offer concrete options**, not to keep saying "next concrete step". A "blocked" exit is a feature, not a failure.

The user's exact words when this happened: *"1"* (one word) and *"now only 1 feed works..."* — the "1" was a one-character response to my "1, 2, or 3" options menu. That is how tight the user‑feedback loop got. When the user starts sending one‑word answers, you have already overstayed the "I will keep trying" posture.

## The fix — pick a smaller tool, in this order

1. **Chunked `patch` from the parent** (THIS IS THE RELIABLE PATH on this host). Apply changes as 4-8 small `patch` calls from the parent, each under ~80 lines of diff, with a `python -c "import ast; ast.parse(...)"` syntax check between batches. Survives any single stream cut because each patch is short enough to complete in one tool call. Resume from the last successful patch on the next turn.

2. **Delegate to a subagent ONLY for a tightly-scoped, sub-300-line task.** A subagent can succeed on a single new reference file, a small new function, or a single patch-style edit. It will *not* succeed on a 700-line full rewrite. If you do delegate, keep the task to one file-or-less and explicit exit conditions.

3. **Bootstrap pattern**: write a small generator script first (`gen.py`) that constructs the big file from embedded strings or by concatenating smaller template files. Then run `python gen.py` to produce the final file. The agent stream only has to carry the generator, not the final file.

4. **Tell the user you are blocked**, and offer the three options above. The "blocked — need user input" exit condition from the standing rules applies here. Do NOT keep restating the loop.

## What NOT to do

- Do not keep saying "next concrete step" in the hope the stream will eventually complete. If it has been cut off twice, the third attempt will almost certainly be cut off too.
- Do not paste the same half-written code three times in a row hoping one of them lands.
- Do not silently leave a half-written file on disk and pretend the work is done.
- Do not delegate a 600+ line full-file rewrite to a subagent — it will time out at 600s with the same effect as a stream cut.
- Do not ask the user to "approve" a delegated full rewrite unless you've already established the loop. They've already approved three times this session; one more approval is a fourth timeout, not progress.

## Evidence from this session

- Attempt 1: `delegate_task` with full rewrite context → `status=timeout, exit_reason=timeout, api_calls=5, duration_seconds=600.0`. File unchanged.
- Attempt 2: parent `write_file` of full file → response cut off mid-stream. File unchanged.
- Attempt 3: parent chunked `patch` x 6 (each <80 lines diff) → all six patches applied, syntax OK, app ran successfully. **This is the pattern that worked.**