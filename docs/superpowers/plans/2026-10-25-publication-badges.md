# Publication Badges Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this small template change.

**Goal:** Distinguish venue/year and presentation information from research topics.
**Architecture:** Wrap metadata and the existing figure together in the left column of `pubRow`; retain the existing data model and routing. Suppress duplicated presentation details in the citation.
**Tech Stack:** Existing HTML/CSS/JavaScript template, Python snapshot renderer, Node test runner.
**Spec:** `docs/superpowers/specs/2026-10-25-publication-badges-design.md`

## Global Constraints

- No changes to Notion schema, credentials, ingestion, filters, links, or images.
- Preserve complete citation and distinct presentation information.
- Validate desktop and mobile layouts without cropping figures or overflowing labels.

## Review Focus

- Missing thumbnail: usable placeholder with venue/year still visible.
- Long journal name or award: wraps without horizontal overflow.
- Presentation already in citation: no repeated suffix, no lost details.
- Multiple research topics: remain visible in the description column.
- Figure enlargement and author/topic filters: still functional.

## Task 1: Update and verify the publication card

**Files:** Modify `template.html`, `tests/test_frontend.cjs`.
**Interfaces:** Existing publication fields `venue_short`, `venue`, `year`, `presentation`, `badge`, `topics`, `thumb`; existing `pubRow(p, activeAuthor)` renderer.

- [x] Run existing frontend tests as baseline (6 passed).
- [x] Add a regression for duplicated presentation text and a control preserving separate details; run the regression before implementing.
- [x] Update publication markup/styles and deduplicate the extra presentation suffix only when the full text is already in the citation.
- [x] Run Python and Node checks and `render.py --snapshot`.
- [x] Inspect a local desktop/mobile preview with ordinary papers, Oral, multiple topics, long venues, and no figure; check image enlargement and filters.
- [x] Obtain a fresh read-only code review, commit the verified change, and provide a reviewable preview/PR.

## Execution notes

User approved the concrete layout and requested implementation. Existing root checkout is preserved; work uses the separate `mlvlab-publication-badges` worktree. Native worktree creation was unavailable because the chat root is not itself a repository, so Git created the worktree from current `origin/main` (`d57bb6b`). Layout styling is verified visually rather than with tests mirroring CSS structure.

Validation: Node 8/8 and Python 33/33 passed; snapshot rendered with all 321 local image references. The duplicate-presentation regression failed before the fix and passed afterward. Chrome desktop and 390px mobile previews covered Oral, multiple topics, a long journal venue, and a missing figure. Figure enlargement and author filtering worked. A separate read-only reviewer found no actionable issues. Changes are prepared for a draft PR; production has not been deployed.
