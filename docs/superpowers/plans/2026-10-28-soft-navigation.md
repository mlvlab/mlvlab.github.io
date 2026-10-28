# Soft Navigation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation and a fresh review of the final diff.

**Goal:** Make MLV navigation feel lighter and transitions smoother without changing its contents.

**Architecture:** Keep the existing synchronous hash router. Use CSS for the adaptive fixed header and mobile panel, and cancellable Web Animations for brief page entry. Reuse the existing template and snapshot preview.

**Tech Stack:** HTML/CSS, vanilla JavaScript, Python renderer, Node test runner.

**Spec:** `docs/superpowers/specs/2026-10-28-soft-navigation-design.md`

## Global Constraints
- Preserve nine routes, all content and publication layout; no dependencies or Notion changes.
- Preview before merging. Use reduced-motion preference consistently.

## Review Focus
- Rapid route changes must show only the newest page.
- Search/deep links must reach their target below the fixed header.
- Mobile menu must close accessibly and fit a short screen.
- Back/forward and unknown routes must still work.
- Animation absence or reduced-motion preference must never hide content.

## Task 1: Adaptive header and mobile menu
**Files:** `template.html` header CSS, markup, initialization.
**Interfaces:** `updateHeader()` toggles scroll appearance; `setMenuOpen(open, restoreFocus=false)` controls menu state. Routing consumes both.
- [x] Add a transparent fixed header, white scroll state, understated animated menu underline, and compact mobile layout.
- [x] Add menu ARIA and Escape handling. Keep current route labels and search.
- [x] Verify desktop, narrow desktop, mobile, scroll and keyboard behavior in the browser.

## Task 2: Page transitions and routing verification
**Files:** `template.html` routing/reveal code; `tests/test_frontend.cjs`.
**Interfaces:** Existing `route()` stays synchronous and preserves RENDER/AFTER. Calls header helpers; cancels any previous entry animation. Reduced motion skips animation.
- [x] Add meaningful tests for route changes, cancellation, reduced motion, target navigation and lifecycle cleanup; observe new assertions fail.
- [x] Add 280ms entry fade with a small vertical shift, keyboard focus management and guarded target scrolling.
- [x] Run Node tests, Python tests, snapshot renderer and diff checks.
- [x] Browser-check actual navigation, rapid clicks, search targets and mobile behavior; request independent review.
- [ ] Save screenshot evidence and publish a reviewable branch/PR with the preview result.

## Validation record
- Baseline frontend tests: 8 passed. Final frontend tests: 15 passed; Python tests: 36 passed.
- Snapshot and current public-content builds passed; content is unchanged.
- Browser checked desktop header, scroll appearance, 1140px fit, 390px menu, Escape, rapid navigation, and search targets.
- Independent review found current-mobile-route focus and sticky-toolbar offsets; both fixed with regression coverage.
