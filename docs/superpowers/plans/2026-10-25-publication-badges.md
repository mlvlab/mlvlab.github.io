# Publication Ribbon Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this small template change.

**Goal:** Apply the user's image-ribbon reference to the existing publication preview.
**Architecture:** Position metadata within the existing visual wrapper; preserve the data model and renderer behaviors.
**Tech Stack:** HTML/CSS/JavaScript template, Python snapshot renderer, Node test runner.
**Spec:** `docs/superpowers/specs/2026-10-25-publication-badges-design.md`

## Constraints and review focus

Preserve Notion ingestion and all publication content. Check long venue labels, missing images, natural figure proportions, mobile spacing, and click-to-enlarge through the labels. Keep the existing regression tests for presentation deduplication.

## Implementation and verification

- [x] Inspect the supplied reference and existing shared hover styles.
- [x] Update `template.html` with larger figures, corner ribbons, whitespace between rows, and no full-row hover box or image scaling.
- [x] Build the snapshot and run frontend/Python checks.
- [x] Inspect desktop/mobile examples and verify the overlay does not block figure enlargement.
- [x] Obtain a focused review and update the existing draft PR with the final design.

The existing `codex/publication-badges` worktree and PR #2 are reused. This is a visual refinement; no new tests that merely mirror CSS are needed. Production deployment is outside this preview step.

Validation: 8 frontend and 33 Python checks passed; snapshot built with 321 images. Desktop and 390px mobile previews checked an Oral paper, multiple topics, the longest venue label, and a missing figure. Clicking the venue ribbon opened the full figure. A separate review found no actionable issues.

Follow-up: the user requested the distinction immediately to the right of the venue. Group the two ribbons in one upper-left flex row, retaining click-through behavior and long-label wrapping.
