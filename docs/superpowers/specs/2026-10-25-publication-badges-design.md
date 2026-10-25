# Publication metadata placement

Approved in chat on 2026-10-25: put venue and year in a separate row immediately above each paper figure, with presentation/award badges beside them. Keep research topics with the paper description. Do not overlay the figure.

## Intent and constraints

- Separate publication venue/distinction from research classification for easier scanning.
- Preserve Notion schema, ingestion, author/topic/year/type filters, links, and figure enlargement.
- Keep full figures uncropped, and keep their metadata attached on mobile.
- Keep complete citation and presentation details; suppress the extra presentation suffix when the citation already contains it.
- Show a quiet publication-type placeholder when no figure exists, avoiding repeated venue/year labels.

## Approaches

1. Overlay labels on the figure: compact, but obscures diagrams and small text.
2. Put a metadata row above the figure: chosen by the user; clear separation without covering content.

## Implementation choices

Use the existing template and styles. Venue/year uses the lab's navy, preprints a neutral tone, distinctions a warm accent. Research-topic labels stay in the text column with quieter styling. Long labels wrap. Source fields and Notion connections remain unchanged.
