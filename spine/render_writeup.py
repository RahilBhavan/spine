"""WRITEUP.md -> site/writeup.html at build time, with a stdlib Markdown subset: #/## headings, paragraphs, **bold**, *italic*,
`code`, [links](url), unordered lists, pipe tables. Two Plotly figures (built client-side from data/backtest.json by site/app.js)
go right after the tables they illustrate (FIGURES). Run: .venv/bin/python -m spine.render_writeup [--stdout]"""
import os, re, html, sys
from spine.api import DATA, load

ROOT = os.path.dirname(DATA)
SRC, OUT = os.path.join(ROOT, 'WRITEUP.md'), os.path.join(ROOT, 'site', 'writeup.html')
FIGURES = {  # table header prefix -> figure emitted right after that table
    '| LLTV |': '''<figure class="fig"><h3>Bad debt by LLTV and crash path, cbBTC, scenario AB</h3><div id="fig-heat" class="chart"></div>
<figcaption>Loss by LLTV and path; the only non-zero cells are the two 2020-2021 paths.</figcaption></figure>''',
    '| Crash |': '''<figure class="fig"><h3>Warning time before crossing 86%, median liquidated position</h3><div id="fig-warn" class="chart chart-short"></div>
<figcaption>Hours between the first margin call and the 86% crossing; every path gives hours to days except March 2020, which gives 25 minutes.</figcaption></figure>''',
}
TEMPLATE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spine writeup: what haircut should Coinbase take?</title>
<meta name="description" content="Seven crash replays of Coinbase's Morpho loan book: on a March 2020 path, liquidator capital, not the LLTV, is what binds.">
<meta property="og:title" content="Spine writeup: what haircut should Coinbase take?">
<meta property="og:description" content="Seven crash replays of Coinbase's Morpho loan book: on a March 2020 path, liquidator capital, not the LLTV, is what binds.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://spine.rahilbhavan.com/site/writeup.html">
<meta property="og:image" content="https://spine.rahilbhavan.com/docs/social-card.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://spine.rahilbhavan.com/site/writeup.html">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='%230f172a'/><text x='32' y='42' text-anchor='middle' font-family='Arial,sans-serif' font-size='28' font-weight='700' fill='%2338bdf8'>SP</text></svg>">
<link rel="stylesheet" href="style.css">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<style>
  .prose { max-width: 860px; margin: 0 auto; }
  .prose .tablewrap { overflow-x: auto; margin: 1em 0; }
  .prose table { border-collapse: collapse; width: 100%; font-size: 0.92em; }
  .prose td, .prose th { white-space: nowrap; }
  .prose th, .prose td { border-bottom: 1px solid var(--grid); padding: 6px 8px; text-align: left; vertical-align: top; }
  .prose th { color: var(--muted); font-weight: 600; }
  .prose h1 { font-size: 1.7em; } .prose h2 { margin-top: 2em; }
  .prose code { background: var(--card); padding: 1px 4px; border-radius: 3px; }
  .prose em { color: var(--muted); }
  .fig { margin: 1em 0; } .fig h3 { font-size: 1em; margin: 1.5em 0 0.25em; color: var(--muted); font-weight: 500; }
  .fig figcaption { color: var(--muted); font-size: 0.92em; margin-top: 0.25em; }
  nav.top { position: sticky; top: 0; z-index: 2; background: var(--bg); padding: 0.5em 0; border-bottom: 1px solid var(--border); }
  nav.top a { margin-right: 1em; }
  nav.toc { background: var(--card); padding: 0.75em 1em; border-radius: 6px; margin: 1em 0; }
  nav.toc ol { margin: 0.25em 0 0; padding-left: 1.5em; } nav.toc p { margin: 0; }
  nav.toc a { display: inline-block; min-height: 24px; }
</style>
</head>
<body>
<main class="prose">
  <nav class="top"><a href="./">Dashboard</a><a href="writeup.html">Writeup</a><a href="../PLAN.md">Plan</a></nav>
  <article id="doc">
@@BODY@@
  </article>
  <footer class="muted">Independent analysis from public on-chain data. Not affiliated with or endorsed by Coinbase or Morpho.</footer>
</main>
<script src="app.js" defer></script>
<script>
addEventListener('DOMContentLoaded', () => loadBacktest().then(bt => { if (bt) { renderHeatmap('fig-heat', bt, 'cbBTC', 'AB'); renderWarn('fig-warn', bt, 'cbBTC'); } }));
</script>
</body>
</html>
'''


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![*\w])\*([^*]+)\*(?!\w)', r'<em>\1</em>', s)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)


def cells(line):
    return [inline(c.strip()) for c in line.strip().strip('|').split('|')]


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', re.sub(r'<[^>]+>', '', text).lower()).strip('-')


def render(md):
    out, para, lst, table = [], [], [], []

    def flush():
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>')
        if lst:
            out.append('<ul>' + ''.join('<li>' + inline(i) + '</li>' for i in lst) + '</ul>')
        if table:
            head, rows = table[0], table[2:]
            out.append('<div class="tablewrap"><table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in cells(head)) + '</tr></thead><tbody>'
                       + ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in cells(r)) + '</tr>' for r in rows) + '</tbody></table></div>')
            out.extend(f for k, f in FIGURES.items() if head.startswith(k))
        para.clear(), lst.clear(), table.clear()

    for line in md.splitlines():
        if not line.strip():
            flush()
        elif line.startswith('#'):
            flush()
            level = len(line) - len(line.lstrip('#'))
            text = inline(line[level:].strip())
            out.append('<h%d%s>%s</h%d>' % (level, ' id="%s"' % slug(text) if level == 2 else '', text, level))
        elif line.startswith('|'):
            table.append(line)
        elif line.startswith('- '):
            lst.append(line[2:])
        else:
            para.append(line.strip())
    flush()
    return '\n'.join(out)


def toc(body, bt):
    links = ''.join('<li><a href="#%s">%s</a></li>' % m for m in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body))
    stamp = '<p><em>Backtest book as of %s; the dashboard refreshes hourly.</em></p>' % bt['latest_book'] if bt else ''
    return '<nav class="toc">%s<ol>%s</ol></nav>' % (stamp, links)


def page():
    body, bt = render(open(SRC).read()), load('backtest')
    i = body.index('</p>', body.index('<p><em>Spine,')) + 4  # TOC and book stamp after the italic intro
    body = body[:i] + '\n' + toc(body, bt) + body[i:]
    return TEMPLATE.replace("@@BODY@@", body)


if __name__ == '__main__':
    h = page()
    if '--stdout' in sys.argv[1:]:
        sys.stdout.write(h)
    else:
        open(OUT, 'w').write(h)
        print('wrote %s (%d bytes, %d tables, %d headings)' % (OUT, len(h), h.count('<table>'), h.count('<h2 ')))
    assert render('| a | b |\n|---|---|\n| **1** | `x` |') == '<div class="tablewrap"><table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td><strong>1</strong></td><td><code>x</code></td></tr></tbody></table></div>'
    assert render('## T\n\ntext *em* [l](u)\n- a\n- b') == '<h2 id="t">T</h2>\n<p>text <em>em</em> <a href="u">l</a></p>\n<ul><li>a</li><li>b</li></ul>'
    assert toc('<h2 id="x-y">X y</h2>', None) == '<nav class="toc"><ol><li><a href="#x-y">X y</a></li></ol></nav>'
    assert h.count('<div class="tablewrap"><table>') == h.count('<table>') == sum(l.startswith('|---') for l in open(SRC))
    assert h.index('<th>LLTV</th>') < h.index('fig-heat') and h.index('<th>Crash</th>') < h.index('fig-warn') and 'marked.min.js' not in h
