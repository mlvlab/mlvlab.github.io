# Publication metadata placement

## Intent

Make venue and presentation distinctions immediately recognizable while keeping research topics with the paper description. The user refined the visual direction using https://hyungjin-chung.github.io/ and explicitly allowed labels on the figures and changes to the existing boxes.

## Design

- Use a navy venue/year ribbon overlapping the upper-left figure corner, inspired by the supplied reference.
- Place Oral, Spotlight, or award text immediately to the right of the venue/year ribbon in the same upper-left row, as requested by the user. Colors remain implementation choices for this preview.
- Increase the desktop figure column to 220px, preserve image proportions, and use a subtle image shadow.
- Separate publication rows with whitespace; remove the full-row hover card, stripe, and image scaling.
- Keep muted research-topic tags in the text column and retain complete citation details.
- Maintain existing Notion fields, filters, links, image enlargement, and missing-image placeholders.

## Alternatives considered

The initial separate metadata row was implemented, but the user's reference clarified that an integrated image label better matches the intended look. A banner across the full image would obscure more of the scientific figure; compact ribbons sharing the upper-left corner are used instead. Clicking a thumbnail still opens the unlabelled full figure.
