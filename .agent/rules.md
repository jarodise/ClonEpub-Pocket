# ClonEpub Workspace Rules

## Overview

These rules govern agent behavior for software/web development projects, consolidating software engineering best practices with agent skill capabilities. The agent MUST follow these rules to maintain code quality, reliability, and user trust.

> **Agent Skills Location:** `~/.gemini/antigravity/skills/`

---

## 1. The Iron Laws

These are non-negotiable. Violations require stopping and restarting the process.

### 1.1 No Fixes Without Root Cause Investigation
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```
- Before proposing ANY fix, use the **systematic-debugging** skill.
- If you haven't completed Phase 1 (Reproduce, Gather Evidence, Trace Data Flow), you cannot propose fixes.
- Random fixes waste time and create new bugs.

### 1.2 No Production Code Without Failing Tests
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```
- Use the **test-driven-development** skill for ALL new features and bug fixes.
- Write test → Watch it FAIL → Write minimal code → Watch it PASS.
- Code written before tests? Delete it. Start over.

### 1.3 No Completion Claims Without Verification
```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```
- Use the **verification-before-completion** skill before ANY success claim.
- Run the verification command IN THIS SESSION. Show the output.
- "Should work" is NOT verification. Evidence before claims, always.

### 1.4 No Git Commits Without Explicit User Approval
- NEVER run `git commit` automatically.
- Always ask user before committing.
- Present staged changes and ask for permission.

---

## 2. Planning & Memory Management

### 2.1 Complex Tasks Require File-Based Planning
For tasks requiring > 5 tool calls, use the **planning-with-files** skill:

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)
→ Anything important gets written to disk.
```

**Create these files in the project directory:**
| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Phases, progress, decisions | After each phase |
| `findings.md` | Research, discoveries | After ANY discovery |
| `progress.md` | Session log, test results | Throughout session |

**Critical Rules:**
- **2-Action Rule:** After every 2 view/browser/search operations, IMMEDIATELY save key findings to files.
- **Read Before Decide:** Before major decisions, read the plan file to refresh goals.
- **Log ALL Errors:** Every error goes in the plan file. This prevents repetition.
- **3-Strike Protocol:** After 3 failures with the same approach, escalate to user.

### 2.2 Brainstorming Before Building
Use the **brainstorming** skill BEFORE any creative work:
- Ask questions one at a time to refine the idea.
- Propose 2-3 approaches with trade-offs.
- Present design in 200-300 word sections, validating each.
- Apply YAGNI ruthlessly.

### 2.3 Writing Implementation Plans
Use the **writing-plans** skill to create detailed plans:
- Save to `docs/plans/YYYY-MM-DD-<feature>.md`.
- Each step should be one action (2-5 minutes).
- Include exact file paths, complete code, and verification commands.

### 2.4 Executing Plans Methodically
Use the **executing-plans** skill:
- Load plan, review critically, identify concerns.
- Execute in batches of 3 tasks.
- Report for review between batches.
- Stop when blocked, don't guess.

---

## 3. Browser Automation

Use the **agent-browser** skill for web interactions, testing, and data extraction.

### 3.1 Core Workflow
```bash
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

### 3.2 Key Commands
| Action | Command |
|--------|---------|
| Navigate | `agent-browser open <url>` |
| Get elements | `agent-browser snapshot -i` |
| Click | `agent-browser click @e1` |
| Fill form | `agent-browser fill @e1 "text"` |
| Screenshot | `agent-browser screenshot` |
| Wait | `agent-browser wait @e1` or `wait --text "Success"` |
| Get text | `agent-browser get text @e1` |

### 3.3 Best Practices
- **Re-snapshot after navigation** - DOM changes invalidate refs.
- **Use `--json` for parsing** - Machine-readable output.
- **Save authentication state** - `agent-browser state save auth.json` for reuse.
- **Debug visually** - Use `--headed` flag to see browser window.

---

## 4. Debugging Flow

When encountering ANY issue, use the **systematic-debugging** skill:

### 4.1 The Four Phases
1. **Root Cause Investigation**
   - Read error messages carefully (they often contain the solution).
   - Reproduce consistently.
   - Check recent changes (git diff).
   - Gather evidence at component boundaries.
   - Trace data flow backward to source.

2. **Pattern Analysis**
   - Find working examples in codebase.
   - Compare working vs broken.
   - Identify every difference.

3. **Hypothesis & Testing**
   - Form single hypothesis: "I think X because Y."
   - Test with SMALLEST possible change.
   - One variable at a time.

4. **Implementation**
   - Create failing test case first (use **test-driven-development** skill).
   - Implement single fix.
   - Verify with evidence.

### 4.2 The 3-Fix Rule
If 3+ fixes fail, STOP:
- Question the architecture, not the symptoms.
- Discuss with user before attempting more fixes.
- This is NOT a failed hypothesis—this is a wrong architecture.

---

## 5. Verification Flow

Use the **verification-before-completion** skill before ANY success claim:

### 5.1 The Gate Function
```
BEFORE claiming any status:
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code
4. VERIFY: Does output confirm the claim?
5. ONLY THEN: Make the claim WITH evidence
```

### 5.2 Common Verifications
| Claim | Requires | NOT Sufficient |
|-------|----------|----------------|
| Tests pass | Test output: 0 failures | Previous run, "should pass" |
| Build succeeds | Build command: exit 0 | Linter passing |
| Bug fixed | Test original symptom | Code changed, assumed fixed |
| Requirements met | Line-by-line checklist | Tests passing |

---

## 6. Available Skills Reference

Invoke these skills when the situation matches:

| Skill | Trigger |
|-------|---------|
| **planning-with-files** | Complex tasks (> 5 tool calls), research, multi-step work |
| **brainstorming** | Before creative work - features, components, modifications |
| **writing-plans** | Converting specs to implementation plans |
| **executing-plans** | Implementing a written plan in batches |
| **systematic-debugging** | Any bug, test failure, unexpected behavior |
| **test-driven-development** | Any new feature or bug fix |
| **verification-before-completion** | Before claiming work is done, fixed, or passing |
| **agent-browser** | Web testing, form filling, screenshots, data extraction |
| **finishing-a-development-branch** | Completing work on a feature branch |
| **using-git-worktrees** | Isolating work in separate Git worktrees |
| **receiving-code-review** | Processing code review feedback |
| **requesting-code-review** | Asking for code review |

---

## 7. Quality Gates

### 7.1 Before Any Build/Bundle
- [ ] All tests pass (run and show output).
- [ ] Lint is clean (run and show output).
- [ ] No dynamic dependencies on local paths (verify binaries).

### 7.2 Before Claiming a Fix
- [ ] Root cause is understood and documented.
- [ ] A failing test reproduces the issue.
- [ ] The fix makes the test pass.
- [ ] No other tests are broken.

### 7.3 Before Distributing
- [ ] Dependencies verified.
- [ ] App bundled and tested.
- [ ] Integration tests pass.
- [ ] Error messages are user-friendly.

---

## 8. Red Flags - Stop and Reconsider

If you catch yourself thinking any of these, STOP:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "I'll write tests after"
- "Skip the test, I'll manually verify"
- "Should work now" (without running verification)
- "One more fix attempt" (after 2+ failures)
- "Tests after achieve the same goals"
- "I don't need to save this to a file, I'll remember"

**All of these mean: STOP. Return to first principles. Use the appropriate skill.**

---

## 9. Communication

- **Be explicit about what you don't know.** Don't guess.
- **Show evidence, not confidence.** Verified output > "I'm sure."
- **Acknowledge mistakes.** If a fix didn't work, say so and explain new approach.
- **Ask clarifying questions** rather than making assumptions.
- **Save findings to files** - Don't rely on context window alone.
