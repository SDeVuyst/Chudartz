import re
from html import unescape

UITSLAGEN_HEADERS = ['Matches', 'Best of 5 - 501']
STAND_HEADERS = ['Naam', 'W1', 'W2', 'W3', 'W4', 'Totaal']
DEFAULT_DATA_ROWS = 3

TABLE_STYLE = 'border-collapse:collapse;width:100%;border:none;'
TH_STYLE = (
    'background:linear-gradient(180deg,#c3111a 0%,#a50e16 100%);'
    'border:none;color:#ffffff;font-family:Montserrat,system-ui,sans-serif;'
    'font-size:0.85rem;font-weight:700;letter-spacing:0.04em;'
    'padding:0.75rem 1rem;text-align:left;text-transform:uppercase;'
)
TD_STYLE = (
    'background-color:#ffffff;border:none;'
    'border-bottom:1px solid rgba(33,37,41,0.1);'
    'color:#212529;font-size:0.95rem;padding:0.7rem 1rem;'
)
STAND_ROW_STYLES = [
    'background-color:#fff9e6;border-left:4px solid #d4af37;',
    'background-color:#f8f8f8;border-left:4px solid #b0b0b0;',
    'background-color:#fff5eb;border-left:4px solid #cd7f32;',
]


def _styled_cell(tag, content, style, extra=''):
    inner = content or '&nbsp;'
    return f'<{tag} style="{style}{extra}">{inner}</{tag}>'


def _build_table(headers, data_rows, css_class, stand=False):
    thead = (
        '<thead><tr>'
        + ''.join(_styled_cell('th', h, TH_STYLE) for h in headers)
        + '</tr></thead>'
    )
    tbody_rows = []
    for i, row in enumerate(data_rows):
        row_style = STAND_ROW_STYLES[i] if stand and i < len(STAND_ROW_STYLES) else ''
        cells = []
        for j, cell in enumerate(row):
            extra = row_style
            if stand and j == 0 and i < len(STAND_ROW_STYLES):
                weight = '800' if i == 0 else '700'
                extra += f'font-weight:{weight};'
                if i == 0:
                    extra += 'font-size:1rem;'
            elif not stand and j == 0:
                extra += 'font-weight:600;'
            cells.append(_styled_cell('td', cell, TD_STYLE, extra))
        tbody_rows.append('<tr>' + ''.join(cells) + '</tr>')
    tbody = '<tbody>' + ''.join(tbody_rows) + '</tbody>'
    return f'<table class="{css_class}" style="{TABLE_STYLE}">{thead}{tbody}</table>'


def default_uitslagen_html():
    return _build_table(
        UITSLAGEN_HEADERS,
        [['', '']] * DEFAULT_DATA_ROWS,
        'league-table league-table--uitslagen',
    )


def default_stand_html():
    return _build_table(
        STAND_HEADERS,
        [['', '', '', '', '', '']] * DEFAULT_DATA_ROWS,
        'league-table league-table--stand',
        stand=True,
    )


def _normalize_cell(cell_html):
    text = re.sub(r'<br\s*/?>', ' ', cell_html, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip()


def extract_table_matrix(html):
    if not html or not html.strip():
        return None
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.I | re.S)
    if not rows:
        return None
    return [
        [_normalize_cell(cell) for cell in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.I | re.S)]
        for row in rows
    ]


def _expected_for_kind(kind):
    if kind == 'uitslagen':
        return UITSLAGEN_HEADERS, DEFAULT_DATA_ROWS
    return STAND_HEADERS, DEFAULT_DATA_ROWS


def is_default_league_table(html, kind):
    if not html or not html.strip():
        return True

    expected_headers, expected_data_rows = _expected_for_kind(kind)
    matrix = extract_table_matrix(html)
    if matrix is None:
        return True

    if len(matrix) != 1 + expected_data_rows:
        return False

    headers = matrix[0]
    if len(headers) != len(expected_headers):
        return False
    if headers != expected_headers:
        return False

    for row in matrix[1:]:
        if len(row) != len(expected_headers):
            return False
        if any(cell for cell in row):
            return False

    return True


def blank_if_default(html, kind):
    return '' if is_default_league_table(html, kind) else (html or '')
