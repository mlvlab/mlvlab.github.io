# Publication venue marks

The frontend recognizes venue abbreviations in Notion's existing `Venue (short)`
and `Venue` fields. No Notion schema change is required. Workshop aliases (for
example `NeurIPSW`, `CVPR Workshop`, `ECCVW`, and `EMNLPW`) inherit the parent
venue's appearance and always display a separate **Workshop** label.

Only abbreviations in the full citation are bold and colored. Citation wording,
years, workshop names, and acceptance/presentation details remain unchanged.
Logos appear only in the badge above the paper's figure. Awards stay to its right.

## Sources checked on 2026-10-29

Colors below are drawn from official assets or sites, except the explicitly noted
editorial choice. They are not all permanent, officially specified brand colors.
Logo files are stored locally to avoid third-party loading dependencies.

| Venue | Text color | Source and logo policy |
| --- | --- | --- |
| NeurIPS | `#68448B` | [Official compact mark](https://neurips.cc/static/core/img/neurips-navbar-logo.svg), saved unchanged as `neurips.svg`; year-neutral. [Media kit](https://neurips.cc/public/MediaKit). |
| ICCV | `#9E1E63` | ICCV 2025 official [poster template](https://media.eventhosts.cc/Conferences/ICCV2025/iccv25_poster_template.pptx), linked from [poster instructions](https://iccv.thecvf.com/Conferences/2025/PosterPrinting). `ppt/media/image1.png` extracted unchanged as `iccv-2025.png`; shown for 2025 only. |
| ECCV | `#231F20` | [Official navbar SVG](https://eccv.ecva.net/static/core/img/eccv-navbar-logo.svg), saved unchanged as `eccv-2026.svg`. Contains Malmö 2026; shown for 2026 only. The original mark is monochrome. |
| AAAI | `#003973` | Primary blue in the [official brand guide](https://aaai.org/wp-content/uploads/2024/06/AAAI-BrandGuidelines-06.2024.pdf), p.29. Text only; [logo use guidance](https://aaai.org/about-aaai/aaai-logos/) requests permission beyond specified uses. |
| CVPR | `#36567C` | Representative navy sampled from the [2026 official site](https://cvpr.thecvf.com/Conferences/2026) logo. Text only: no suitable standalone compact asset verified. |
| ICLR | `#387D25` | [Official compact mark](https://iclr.cc/static/core/img/iclr-navbar-logo.svg), saved unchanged as `iclr.svg`; year-neutral. Text green is a darker UI adaptation of the logo's bright `#60C332` for legibility. |
| ICML | `#2A419E` | Blue in the [official compact mark](https://icml.cc/static/core/img/icml-navbar-logo.svg), saved unchanged as `icml.svg`; year-neutral. Its light head is displayed on a dark tile without recoloring. |
| WACV | `#115D73` | Representative teal from the [2026 official conference](https://wacv.thecvf.com/Conferences/2026) poster logo. Text only. The current navbar depicts 2027 and must not be reused for other years. |
| IJCV | `#2B6280` | Editorial blue, not a certified journal brand color. No journal-specific compact logo verified at the [official journal site](https://link.springer.com/journal/11263); publisher logos are not substituted. |
| EMNLP | `#D12632` | Red in the [2026 official logo](https://2026.emnlp.org/assets/images/logos/emnlp_2026_logo_v1.png). Text only: annual city/year lockups are too wide for a small badge and are not a permanent mark. |
| ACL | `#C51920` | Darker UI adaptation of `#ED1E24` in the [year-neutral association mark](https://2027.aclweb.org/assets/images/acl-plain-logo.png), saved unchanged as `acl.png`. Used for ACL, not as an invented dedicated EMNLP/NAACL logo. |
| NAACL | `#02678F` | Link/accent blue from the [2025 official website CSS](https://2025.naacl.org/assets/css/main.css). Text only; not a verified permanent brand specification. |

## Maintenance

`VENUE_BRANDS` in `template.html` holds each color and optional logo. The `logo`
field is reserved for year-neutral marks; `logos` maps publication years to
year-specific files. Unknown years fall back to colored text. Unknown venues and
preprints retain the existing neutral style. `render.py` copies these files for
both Notion builds and snapshot recovery builds.

When adding a venue, update the acronym matcher and registry together. Keep the
original logo and source URL, verify year restrictions, and check both mobile
and desktop badges with awards and workshop labels.
