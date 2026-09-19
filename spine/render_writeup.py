"""WRITEUP.md -> site/writeup.html at build time, with a stdlib Markdown subset: #/## headings, paragraphs, **bold**, *italic*,
`code`, [links](url), unordered lists, pipe tables. Two Plotly figures (built client-side from data/backtest.json by site/app.js)
go at the top of section 4. Run: python3.12 -m spine.render_writeup [--stdout]"""
import os, re, html, sys
from spine.api import DATA, load

ROOT = os.path.dirname(DATA)
SRC, OUT = os.path.join(ROOT, 'WRITEUP.md'), os.path.join(ROOT, 'site', 'writeup.html')
FIGURES_AFTER = '## 4.'  # heading prefix that gets the figures inserted after it
FIGURES = '''<div class="fig"><h3>Bad debt by LLTV and crash path, cbBTC, scenario AB</h3><div id="fig-heat" class="chart"></div></div>
<div class="fig"><h3>Warning time before crossing 86%, median liquidated position</h3><div id="fig-warn" class="chart chart-short"></div></div>'''
TEMPLATE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spine: haircut writeup</title>
<link rel="stylesheet" href="style.css">
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
  .prose { max-width: 860px; margin: 0 auto; }
  .prose table { border-collapse: collapse; width: 100%; table-layout: fixed; margin: 1em 0; font-size: 0.92em; }
  .prose td, .prose th { overflow-wrap: anywhere; white-space: normal; }
  .prose th, .prose td { border-bottom: 1px solid var(--grid); padding: 6px 8px; text-align: left; vertical-align: top; }
  .prose th { color: var(--muted); font-weight: 600; }
  .prose h1 { font-size: 1.7em; } .prose h2 { margin-top: 2em; }
  .prose code { background: var(--card); padding: 1px 4px; border-radius: 3px; }
  .prose em { color: var(--muted); }
  .fig h3 { font-size: 1em; margin: 1.5em 0 0.25em; color: var(--muted); font-weight: 500; }
  nav a { margin-right: 1em; }
</style>
</head>
<body>
<main class="prose">
  <nav><a href="./">Dashboard</a><a href="writeup.html">Writeup</a><a href="../PLAN.md">Plan</a></nav>
  <article id="doc">
@@BODY@@
  </article>
</main>
<script src="app.js"></script>
<script>
loadBacktest().then(bt => { if (bt) { renderHeatmap('fig-heat', bt, 'cbBTC', 'AB'); renderWarn('fig-warn', bt, 'cbBTC'); } });
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


def render(md):
    out, para, lst, table = [], [], [], []

    def flush():
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>')
        if lst:
            out.append('<ul>' + ''.join('<li>' + inline(i) + '</li>' for i in lst) + '</ul>')
        if table:
            head, rows = table[0], table[2:]
            out.append('<table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in cells(head)) + '</tr></thead><tbody>'
                       + ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in cells(r)) + '</tr>' for r in rows) + '</tbody></table>')
        para.clear(), lst.clear(), table.clear()

    for line in md.splitlines():
        if not line.strip():
            flush()
        elif line.startswith('#'):
            flush()
            level = len(line) - len(line.lstrip('#'))
            out.append('<h%d>%s</h%d>' % (level, inline(line[level:].strip()), level))
            if line.startswith(FIGURES_AFTER):
                out.append(FIGURES)
        elif line.startswith('|'):
            table.append(line)
        elif line.startswith('- '):
            lst.append(line[2:])
        else:
            para.append(line.strip())
    flush()
    return '\n'.join(out)


def page():
    body, bt = render(open(SRC).read()), load('backtest')
    if bt:  # book date stamp after the italic intro
        i = body.index('</p>', body.index('<p><em>Spine,')) + 4
        body = body[:i] + '\n<p><em>Backtest book as of %s; the dashboard refreshes hourly.</em></p>' % bt['latest_book'] + body[i:]
    return TEMPLATE.replace("@@BODY@@", body)


if __name__ == '__main__':
    h = page()
    if '--stdout' in sys.argv[1:]:
        sys.stdout.write(h)
    else:
        open(OUT, 'w').write(h)
        print('wrote %s (%d bytes, %d tables, %d headings)' % (OUT, len(h), h.count('<table>'), h.count('<h2>')))
    assert render('| a | b |\n|---|---|\n| **1** | `x` |') == '<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td><strong>1</strong></td><td><code>x</code></td></tr></tbody></table>'
    assert render('## T\n\ntext *em* [l](u)\n- a\n- b') == '<h2>T</h2>\n<p>text <em>em</em> <a href="u">l</a></p>\n<ul><li>a</li><li>b</li></ul>'
    assert h.count('<table>') == sum(l.startswith('|---') for l in open(SRC)) and 'fig-heat' in h and 'marked.min.js' not in h
