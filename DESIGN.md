# Spine interface system

Version: workstation-1, 2026-10-26. Extends the established Spine identity. Operate mode with readable research detail.

## Direction
A precise risk workstation. Real market comparisons and a price-shock inspection tool provide the character. The brand stays blue; semantics stay textual as well as colored. No decorative imagery, poster typography, marketing claims, ornamental gauges, or animated market movement.

## Tokens and composition
Reuse `site/style.css`'s light/dark color roles. `site/workspace.css` owns this dashboard's structural extension; the writeup keeps its established reading layout. System sans, tabular numerals, 15px body, 13–14px secondary text; headings 20–28px, answer values up to 36px on desktop and 26px on phone. Native controls at least 40px high, 44px on touch layouts. Spacing: 4/8/12/16/24/32/48. Focus: visible blue outline, explicit high-contrast fallback.

Desktop: fixed section rail, broad working column, sticky market toolbar, answer/evidence composition. Tablet: top navigation. Phone: compact top navigation, wrapping toolbar, condensed answer rows, four-column market table with secondary fields deferred, full inspection workflow. No page-wide horizontal scrolling.

## Components
Risk answers are one definition list, not three interchangeable cards. Watchlist rows carry market identity, observed borrow, estimated threshold, named state and selection. Price shock is a native slider plus a three-row comparison table sourced directly from the saved curve; it is an instantaneous snapshot inspection, not the dynamic backtest. Dollar comparison bars, when used, share a zero baseline and denominator and carry direct labels.

Selected market is global; filter/sort and inspected shock are URL state. Theme preference is local and respects system mode until explicitly changed. Navigation marks the visible section. Copy-link feedback stays beside the action. Loading/failure/empty states name what is unavailable and retain the usable evidence.

## Boundaries
Capacity is modeled. A null crossing means no crossing through the sampled 70% fall, not zero or a known exact 70%. Do not subtract it as a number. Raw curve buckets must be selected exactly; never interpolate positions or infer realized loss. Preserve the explicit scenario on each comparison. Public visual approval requires an exact-artifact review record; an automated score is not human comprehension.

## Blue graph extension — spine-blue-graphs-1

On 2026-10-26 the user explicitly authorized blue in place of Rahil Design's usual yellow for Spine's graphs. This is a project-local override; the global public design bundle is unchanged. `site/chart-system.css` owns the graph roles: white surface, dark neutral ink, gray context, blue `#0052ff`, pale blue area fill, muted grid. Graphs retain light figure surfaces in both application themes.

Blue identifies the value or relationship named by the graph's comparison sentence. Other series use neutral tones, explicit text and dash patterns. Heatmap dollar labels have opaque white backing, so contrast never depends on blue intensity. Missing cells say Not run; numeric zeros say $0. A fixed dollar color scale is used across scenarios and capital settings for one market and selected measure; changing market or measure may change the labeled scale.

Phone heatmaps transpose to five LLTV columns, warning bars are horizontal, and all Plotly SVG labels are at least12 CSS pixels in the verified contexts. These are interactive app figures, not social/feed exports; the social-card18px/40px displayed-feed rules are not claimed by this interface. Every figure includes a named keyboard-toggleable table, a direct comparison summary and its source/date/scope. Bars have zero-based linear axes. A logarithmic histogram is represented as dots, and log curves omit zeros explicitly while retaining them in the table.
