# Admin Access Policy — Just Trades Platform

> **Defines access levels, onboarding stages, and safety boundaries for admin team members.**
> **Last updated: Feb 21, 2026**

---

## OVERVIEW

Admins are onboarded in two stages to prevent accidental production changes:

| Stage | Access Level | What They Can Do | What They Can't Do |
|-------|-------------|------------------|-------------------|
| **Stage 1: Read-Only** | Reference doc + Claude Code | Monitor, diagnose, learn the system | Edit code, deploy, restart, modify DB |
| **Stage 2: Repo Access** | Full GitHub repo + Claude Code | Submit PRs, review code, propose changes | Push directly to main (branch protection) |

---

## STAGE 1: READ-ONLY REFERENCE (Initial Onboarding)

### What They Receive

1. **`CLAUDE_ADMIN_REFERENCE.md`** — Standalone system manual (read-only version of CLAUDE.md)
2. **`README_FOR_ADMINS.md`** — Setup guide for Claude Code + quick reference

### How It Works

- Admin creates a local directory (`~/just-trades-admin/`)
- Places `CLAUDE_ADMIN_REFERENCE.md` as `CLAUDE.md` in that directory
- Runs `claude` from that directory — Claude Code loads the reference automatically
- They can ask Claude questions, run monitoring curl commands, and learn the system

### What's Included

- All 31 safety rules (summary table format)
- Full architecture documentation
- Production strategy configs for every recorder
- All monitoring endpoints with safe GET curl commands
- Debugging checklists and incident response procedures
- 24 documented production disasters and their fixes
- Daily monitoring checklist
- Common failure scenarios with diagnosis steps

### What's Excluded (Safety)

- All destructive commands removed: `git reset`, `git push -f`, `railway restart`
- No SQL mutation commands: no `UPDATE`, `DELETE`, `INSERT`
- No Railway CLI admin commands: no `railway variables --set`, `railway up`
- No cache clearing or queue manipulation
- No code editing instructions

### What They CAN Do

| Action | Example |
|--------|---------|
| Monitor service health | `curl -s "https://justtrades.app/health"` |
| Check broker workers | `curl -s "https://justtrades.app/api/broker-execution/status"` |
| Check for failures | `curl -s "https://justtrades.app/api/broker-execution/failures"` |
| Check WebSocket status | `curl -s "https://justtrades.app/api/tradingview/status"` |
| Check account auth | `curl -s "https://justtrades.app/api/accounts/auth-status"` |
| Check Whop sync | `curl -s "https://justtrades.app/api/admin/whop-sync-status"` |
| Run smoke test | Full smoke test script (all GET endpoints) |
| Ask Claude questions | "How does DCA work?", "What does Rule 12 mean?" |
| Read monitoring docs | All endpoint reference material |

### What Requires Owner Approval

| Action | Why |
|--------|-----|
| Restarting Railway service | Could interrupt active trades |
| Running database migrations | Could break schema |
| Modifying any code file | Sacred files restrictions |
| Changing environment variables | Could break integrations (Whop, Brevo, Tradovate) |
| Clearing caches or queues | Could lose in-flight trade data |
| Deleting users or trade records | Irreversible data loss |
| Force-pushing to git | Could destroy production state |
| Changing trader/recorder settings | Could affect live trading |

### Why This Is Safe

1. **No repo access** — They don't have the code, can't edit it
2. **No Railway CLI link** — Can't restart, redeploy, or change env vars
3. **No git credentials** — Can't push anything to the repository
4. **No DB credentials** — Can't run SQL against production
5. **No destructive commands in the doc** — Reference file has been sanitized
6. **Claude Code is scoped to their local directory** — Only file is the reference doc

---

## STAGE 2: REPOSITORY ACCESS (After Training)

### Prerequisites Before Granting Repo Access

- [ ] Admin has completed Stage 1 (read-only learning period)
- [ ] Admin demonstrates understanding of the 31 rules
- [ ] Admin can correctly answer: "What are the sacred files and why?"
- [ ] Admin can correctly answer: "What happens if you change background threads to synchronous?"
- [ ] Admin has signed the admin contract
- [ ] Owner has set up branch protection on `main`

### Branch Protection Setup (GitHub)

Before granting repo access, configure these branch protection rules on `main`:

```
Repository Settings → Branches → Branch protection rules → Add rule

Branch name pattern: main

Required:
✅ Require a pull request before merging
✅ Require approvals (minimum: 1 — owner must approve)
✅ Dismiss stale pull request approvals when new commits are pushed
✅ Require status checks to pass before merging

Optional but recommended:
✅ Require conversation resolution before merging
✅ Restrict who can push to matching branches (owner only)
```

### What Changes at Stage 2

| Capability | Stage 1 | Stage 2 |
|-----------|---------|---------|
| Read system documentation | Yes | Yes |
| Monitor production endpoints | Yes | Yes |
| Read production code | No | Yes |
| Edit code locally | No | Yes |
| Create branches | No | Yes |
| Submit pull requests | No | Yes |
| Push directly to main | No | **No** (branch protection) |
| Approve PRs | No | No (owner only) |
| Deploy to Railway | No | No (owner only) |
| Manage env vars | No | No (owner only) |
| Run DB migrations | No | No (owner only) |

### Onboarding to Repo Access

1. **Add admin as collaborator** on GitHub (Write access, not Admin)
2. **Admin clones the repo**: `git clone <repo-url>`
3. **Admin runs Claude Code from the repo**: `cd just-trades-platform && claude`
4. **Claude Code loads the full CLAUDE.md** (not the read-only version)
5. **Admin creates feature branches**: `git checkout -b admin/feature-name`
6. **All changes go through PRs** — owner reviews and approves before merge
7. **Auto-deploy triggers on merge to main** — only after owner approval

### Rules That Apply to All Admins (Both Stages)

1. **Never modify sacred files** without explicit owner approval
2. **Never bundle feature additions with core engine changes** (Rule 9 lesson)
3. **One commit = one concern** — never mix unrelated changes
4. **Test with a real signal** before marking any change as working
5. **Read the relevant doc** before touching any code area (Mandatory Protocol)
6. **Never change background threads to synchronous** — this caused a 100% outage
7. **Never downgrade pool sizes, remove safety nets, or strip settings**

---

## FILES REFERENCE

| File | Location | Purpose |
|------|----------|---------|
| `CLAUDE_ADMIN_REFERENCE.md` | Sent to admins (not in repo) | Read-only system manual for Stage 1 |
| `README_FOR_ADMINS.md` | Sent to admins (not in repo) | Setup guide for Claude Code |
| `CLAUDE.md` | Repo root | Full system blueprint (loaded by Claude Code) |
| `docs/ADMIN_ACCESS_POLICY.md` | Repo docs | This file — access levels and onboarding |

### Generating Updated Admin Reference

When CLAUDE.md is updated, regenerate the admin reference:

1. Read the current `CLAUDE.md`
2. Strip all destructive commands (git reset, push -f, railway restart, SQL mutations)
3. Convert rules to summary table format
4. Add "Read-Only Reference" header
5. Add "What you CAN do" / "What requires owner approval" sections
6. Save as `CLAUDE_ADMIN_REFERENCE.md`
7. Send to all active admins

---

## REVOKING ACCESS

### Stage 1 (Read-Only)
- No action needed — the reference file is a static document
- If monitoring endpoints need to be restricted, add API key requirements

### Stage 2 (Repo Access)
1. Remove collaborator from GitHub repository
2. Verify branch protection rules still active
3. Audit any open PRs from the admin
4. Rotate any shared secrets if the admin had access to env vars

---

*Source: Admin access policy for Just Trades platform. Established Feb 21, 2026.*
