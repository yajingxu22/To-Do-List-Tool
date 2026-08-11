#!/usr/bin/env python3
"""To-Do List Tool - PDF parser + web server (pdfplumber)."""

import os, sys, re, json, uuid, tempfile, webbrowser
from datetime import datetime

DATE_PAT = re.compile(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?')
EXAM_KW = re.compile(r'\b(final\s*(exam|assessment)?|midterm|exam\b|quiz\b|assessment)\b', re.I)

def parse_date(text, default_year=2026):
    if not text: return None
    text = text.replace('\n', ' ')
    m = DATE_PAT.search(text)
    if not m: return None
    month, day = int(m.group(1)), int(m.group(2))
    if m.group(3):
        yr = int(m.group(3))
        if yr < 100: yr += 2000
    else:
        yr = default_year
    try: return datetime(yr, month, day)
    except: return None

def find_header_columns(table):
    for ri, row in enumerate(table[:4]):
        if not row: continue
        texts = [str(c).lower().strip() if c else '' for c in row]
        rc, ac, dc = [], [], []
        for i, t in enumerate(texts):
            if 'reading' in t or 'media' in t: rc.append(i)
            if 'assignment' in t or 'due' in t: ac.append(i)
            if t in ('date', 'week'): dc.append(i)
        if rc and ac:
            all_r = set()
            for c in rc:
                for o in [c-1, c, c+1]:
                    if 0 <= o < len(texts): all_r.add(o)
            all_a = set()
            for c in ac:
                for o in [c-1, c, c+1]:
                    if 0 <= o < len(texts): all_a.add(o)
            all_r -= all_a
            return {'reading_cols': sorted(all_r), 'assignment_cols': sorted(all_a),
                    'date_cols': sorted(dc) if dc else [3,4,5], 'header_row': ri, '_width': len(row)}
    return None

def find_all_outline_tables(all_pages_tables):
    segments, found_cols, outline_width = [], None, None
    for page_tables in all_pages_tables:
        for table in page_tables:
            if not table or len(table) < 2: continue
            cols = find_header_columns(table)
            if cols:
                found_cols, outline_width = cols, cols['_width']
                start = cols['header_row'] + 1
                if start < len(table):
                    nr = table[start]
                    if nr:
                        c0 = str(nr[0]).strip().lower() if nr[0] else ''
                        c1 = str(nr[1]).strip().lower() if len(nr)>1 and nr[1] else ''
                        if c0 in ('week','module') or c1 in ('week','module'): start += 1
                data = table[start:]
                if data: segments.append((data, found_cols))
            elif found_cols and len(table) > 2:
                rw = len(table[0]) if table[0] else 0
                if abs(rw - outline_width) <= 2:
                    # Continuation table - accept even without dates in first row
                    segments.append((table, found_cols))
    return segments, found_cols

def extract_cell_text(row, col_indices):
    """Extract text from columns, deduplicating content across adjacent sub-columns."""
    texts = []
    for ci in col_indices:
        if ci < len(row) and row[ci]:
            t = str(row[ci]).strip()
            if t and t not in texts:  # deduplicate across sub-columns
                texts.append(t)
    return ' '.join(texts)

def get_row_date(row, date_cols, dy=2026):
    if len(row) > 3 and row[3]:
        d = parse_date(str(row[3]), dy)
        if d: return d
    for ci in date_cols:
        if ci < len(row) and row[ci]:
            d = parse_date(str(row[ci]), dy)
            if d: return d
    return None

def clean_title(text):
    text = text.replace('\n', ' ')
    # Strip bullet prefix
    text = re.sub(r'^[\u2022\u00b7\*\-]\s*', '', text.strip())
    # Strip action prefixes
    text = re.sub(r'^(READ|SUBMIT|PREPARE|EXPLORE|COMPLETE|WATCH|REVIEW)\s*:?\s*', '', text, flags=re.I)
    # Strip trailing metadata
    text = re.sub(r'\s*[—\-]+\s*focus on.*$', '', text, flags=re.I)
    text = re.sub(r'\s*via Course Site.*$', '', text, flags=re.I)
    text = re.sub(r'\s*on (Course Site|the course site).*$', '', text, flags=re.I)
    text = re.sub(r'\s*Due (by|in).*$', '', text, flags=re.I)
    text = re.sub(r'\s*\(handed out.*$', '', text, flags=re.I)
    text = re.sub(r'\s*Location\s+\w.*$', '', text, flags=re.I)
    text = re.sub(r'^["\u201c\u201d]+|["\u201c\u201d]+$', '', text.strip())
    return text.strip(' .,;:')

def is_skip(text):
    t = text.strip()
    # Strip bullet prefix before checking
    t = re.sub(r'^[\u2022\u00b7\*\-]\s*', '', t)
    t = t.lower().strip()
    if re.match(r'^n/?a\b', t): return True
    if re.match(r'^none\.?$', t): return True
    if not t or len(t) < 2: return True
    return False

def parse_embedded_date(text, dy=2026):
    m = re.search(r'[Dd]ue\s+(?:by\s+)?(\d{1,2}/\d{1,2}(?:/\d{2,4})?)', text)
    return parse_date(m.group(1), dy) if m else None

def split_items(text):
    """Split concatenated bullet items."""
    text = text.replace('\n', ' ')
    # Split on bullet character (with optional leading whitespace)
    parts = re.split(r'\s*[\u2022]\s*', text)
    items = [p.strip() for p in parts if p.strip()]
    if not items:
        items = [text.strip()] if text.strip() else []
    return items

def scan_for_exams(segments, dy=2026):
    """Global scan across ALL columns (especially title/topics) for exam/quiz keywords."""
    exam_items = []
    for rows, cols in segments:
        rs, aset = set(cols['reading_cols']), set(cols['assignment_cols'])
        dc = cols['date_cols']
        cur_date = None
        for row in rows:
            if not row: continue
            rd = get_row_date(row, dc, dy)
            if rd: cur_date = rd
            for ci in range(len(row)):
                if ci in rs or ci in aset: continue
                if ci in dc: continue
                cell = row[ci]
                if not cell: continue
                text = str(cell).strip()
                if EXAM_KW.search(text) and cur_date:
                    title = clean_title(text)
                    if title and len(title) >= 3 and not is_skip(title):
                        exam_items.append({'type':'quiz','title':title,'date':cur_date})
    return exam_items

def parse_all_segments(segments, dy=2026):
    """Parse all table segments, carrying date across page boundaries."""
    items = []
    last_date = None  # Carry across page boundaries
    for rows, cols in segments:
        dc = cols['date_cols']
        rc = cols['reading_cols']
        ac = cols['assignment_cols']
        cur_date = last_date  # Use last date from previous page if no date in first row
        cur_read, cur_assign = [], []
        def flush():
            nonlocal cur_date, cur_read, cur_assign
            if cur_date is None:
                cur_read, cur_assign = [], []
                return
            fr = ' '.join(cur_read).strip()
            if fr:
                for raw in split_items(fr):
                    if not is_skip(raw):
                        t = clean_title(raw)
                        if t and len(t) >= 2:
                            items.append({'type':'reading','title':t,'date':cur_date})
            fa = ' '.join(cur_assign).strip()
            if fa:
                for raw in split_items(fa):
                    if not is_skip(raw):
                        t = clean_title(raw)
                        if t and len(t) >= 2:
                            ed = parse_embedded_date(raw, dy)
                            d = ed if ed else cur_date
                            tl = t.lower()
                            tp = 'quiz' if any(k in tl for k in ['final','exam','midterm','assessment','quiz']) else 'assignment'
                            items.append({'type':tp,'title':t,'date':d})
            cur_read, cur_assign = [], []
        for row in rows:
            if not row: continue
            rd = get_row_date(row, dc, dy)
            if rd:
                flush()
                cur_date = rd
            rt = extract_cell_text(row, rc)
            if rt: cur_read.append(rt)
            at = extract_cell_text(row, ac)
            if at: cur_assign.append(at)
        flush()
        last_date = cur_date
    return items

def deduplicate(items):
    seen, result = [], []
    for item in items:
        tw = set(re.findall(r'\w{3,}', item['title'].lower()))
        dup = False
        for si, sw in seen:
            if item["date"] != si["date"]: continue
            if item["type"] != si["type"]: continue
            if not tw or not sw: continue
            if len(tw & sw) / max(len(tw | sw), 1) >= 0.5:
                dup = True; break
        if not dup:
            seen.append((item, tw))
            result.append(item)
    return result

def parse_pdf(pdf_path, course_name='', default_year=2026):
    import pdfplumber
    apt = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            apt.append(page.extract_tables() or [])
    segments, cols = find_all_outline_tables(apt)
    if not segments: return []
    items = parse_all_segments(segments, default_year)
    items.extend(scan_for_exams(segments, default_year))
    items = deduplicate(items)
    return [{'id':str(uuid.uuid4()),'course':course_name,'type':it['type'],'title':it['title'],
             'description':'','dueDate':it['date'].strftime('%Y-%m-%dT23:59:00'),'completed':False,
             'isUserAdded':False,'pinned':False,'manualUrgencyBoost':0,'customUrgencyScore':None,
             'recurrence':None,'urgency':0} for it in items]

def cli_mode():
    import argparse
    p = argparse.ArgumentParser(description='Parse syllabus PDF into to-do JSON.')
    p.add_argument('pdf')
    p.add_argument('--course', default='')
    p.add_argument('--output', default=None)
    p.add_argument('--year', type=int, default=2026)
    a = p.parse_args()
    items = parse_pdf(a.pdf, a.course, a.year)
    out = a.output or a.pdf.rsplit('.',1)[0] + '_todos.json'
    with open(out,'w') as f: json.dump(items, f, indent=2)
    print(f'Extracted {len(items)} items -> {out}')

def server_mode():
    from flask import Flask, request, jsonify, send_file
    app = Flask(__name__)
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    @app.after_request
    def cors(resp):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = '*'
        return resp
    @app.route('/')
    def index(): return send_file(html_path)
    @app.route('/health')
    def health(): return jsonify({'status':'ok'})
    @app.route('/parse', methods=['POST'])
    def parse():
        if 'file' not in request.files:
            return jsonify({'error':'No file'}), 400
        f = request.files['file']
        course = request.form.get('course','')
        year = int(request.form.get('year', 2026))
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        f.save(tmp.name)
        try:
            items = parse_pdf(tmp.name, course, year)
            return jsonify({'items':items,'count':len(items)})
        except Exception as e:
            return jsonify({'error':str(e)}), 500
        finally:
            os.unlink(tmp.name)
    port = int(os.environ.get('PORT', 5050))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    print(f'\n  To-Do List Tool running at http://{host}:{port}\n')
    if not os.environ.get('PORT'):
        webbrowser.open(f'http://127.0.0.1:{port}')
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1].endswith('.pdf'):
        cli_mode()
    else:
        server_mode()
