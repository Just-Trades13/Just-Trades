# PRE-CHANGE CHECKLIST - READ THIS BEFORE MAKING ANY CHANGES

## ⚠️ CRITICAL: User Cannot Afford to Break Working Code

**STOP. Read this checklist BEFORE making ANY changes to working code.**

## Step 1: Verify the Problem Exists

- [ ] User has explicitly reported a problem
- [ ] I can reproduce the problem
- [ ] I understand what the user is seeing vs. what they expect
- [ ] I've checked the database to see actual data state
- [ ] I've checked the UI to see what users actually see
- [ ] I've checked server logs to understand the actual state

**If ANY checkbox is unchecked, STOP. Do not make changes.**

## Step 2: Check WHAT_NOT_TO_DO.md

- [ ] I've read WHAT_NOT_TO_DO.md
- [ ] I understand what NOT to do
- [ ] My planned change is NOT on the "don't do" list
- [ ] I'm not repeating a previous mistake

**If you're about to do something on the "don't do" list, STOP. Don't do it.**

## Step 3: Verify Code is Actually Broken

- [ ] The code has a clear bug (error, exception, wrong output)
- [ ] The code is NOT working as expected
- [ ] The user has confirmed it's broken
- [ ] I've tested it myself and confirmed it's broken

**If code is working, DO NOT CHANGE IT.**

## Step 4: Make Minimal Changes

- [ ] I'm making ONE small change at a time
- [ ] I can revert this change easily if it breaks
- [ ] I'm not changing multiple things at once
- [ ] I'm not "improving" code that works

**If you're making multiple changes or "improvements", STOP. Make one small change.**

## Step 5: Test After Each Change

- [ ] I've tested the change
- [ ] The change fixes the problem
- [ ] The change doesn't break anything else
- [ ] I can revert if needed

**If you can't test or revert, DON'T MAKE THE CHANGE.**

## Red Flags - STOP IMMEDIATELY

If you see any of these, STOP and ask the user:

- 🔴 Logs show warnings but everything works
- 🔴 Code is working but "could be better"
- 🔴 You think something "might" be wrong
- 🔴 User hasn't reported any issues
- 🔴 You're "improving" error handling
- 🔴 You're "optimizing" working code
- 🔴 You're adding "better" logging
- 🔴 You're changing endpoint order "just in case"
- 🔴 You're adding comments about potential problems

## When in Doubt

**ASK THE USER. DO NOT ASSUME.**

## Recovery Process

If something breaks:
1. **STOP making changes immediately**
2. **Revert to last known working state**
3. **Tell the user what happened**
4. **Only then** make minimal fixes if needed

