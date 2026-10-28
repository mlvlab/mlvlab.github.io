# Softer navigation and page transitions

The user requests the feel of https://uilab.kr/ for menus and page changes, preserving the existing menu items and content. The reference uses a transparent header over photography, a light header after scrolling, and gradual menu color changes.

## Scope and approach

Retain all nine routes, Notion data, banners, publication layout, search, filters, and links. Adapt the reference's header behavior to MLV's navy identity: transparent over existing banners, white after scrolling, lighter menu typography and animated underlines. Add a short fade with minimal upward movement when page content changes. Mobile navigation opens softly and remains keyboard accessible.

An animation-only change would leave the heavy solid header intact. Rebuilding the site or replacing content would exceed the request. Use the existing template and no new dependencies. Timing and spacing are implementation choices; prepare a local preview for visual review before merging.

## Behavior and constraints

- Route replacement remains synchronous; cancel prior entry animation on rapid navigation.
- Preserve lifecycle setup, carousel cleanup, search targets, browser history, and unknown-route fallback.
- Respect reduced motion for transitions and scrolling; content remains visible without animation support.
- Keep menu state accessible with aria-current, aria-expanded, Escape closure and focus handling.
- No Notion schema, content, images, database connection, or deployment changes.
