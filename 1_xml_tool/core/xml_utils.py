# -*- coding: utf-8 -*-
"""XML 定位與精準替換工具。

設計原則：
    絕不用 ElementTree 重新序列化整份檔案。鼎新 BPM 的 .form / .bpmn 對
    縮排、屬性順序、逃脫寫法(&quot;)、無 XML 宣告頭等格式細節敏感，
    重新序列化容易造成匯回失敗。本模組只做「定位 → 字串替換」，
    未被指定替換的位元組會原封不動保留。
"""

import re
from collections import namedtuple

# 一次匹配一個標籤；屬性值內的 > 已用引號保護
_TAG_RE = re.compile(
    r'<(/?)([A-Za-z_][A-Za-z0-9_.\-:]*)((?:"[^"]*"|\'[^\']*\'|[^>\'"])*?)\s*(/?)>'
)

# name        標籤名
# start/end   含開頭標籤與結尾標籤的完整範圍
# inner_start/inner_end  標籤內容(不含標籤本身)的範圍
Span = namedtuple('Span', 'name start inner_start inner_end end attrs')


def read_xml(path):
    """以位元組讀入後解碼，避免換行被轉換。回傳 (文字, BOM字串)。"""
    with open(path, 'rb') as f:
        raw = f.read()
    bom = ''
    if raw.startswith(b'\xef\xbb\xbf'):
        bom = '\ufeff'
        raw = raw[3:]
    return raw.decode('utf-8'), bom


def write_xml(path, text, bom=''):
    with open(path, 'wb') as f:
        if bom:
            f.write(b'\xef\xbb\xbf')
        f.write(text.encode('utf-8'))


def iter_tags(text, start=0, end=None):
    end = len(text) if end is None else end
    pos = start
    while True:
        m = _TAG_RE.search(text, pos, end)
        if not m:
            return
        yield m
        pos = m.end()


def find_blocks(text, predicate, start=0, end=None):
    """找出所有 predicate(標籤名) 為真的平衡區塊（任意深度）。"""
    stack = []
    out = []
    for m in iter_tags(text, start, end):
        closing, name, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    st = stack[i]
                    del stack[i:]
                    if predicate(name):
                        out.append(Span(name, st[1], st[2], m.start(), m.end(), st[3]))
                    break
        elif selfclose:
            if predicate(name):
                out.append(Span(name, m.start(), m.end(), m.end(), m.end(), attrs))
        else:
            stack.append((name, m.start(), m.end(), attrs))
    out.sort(key=lambda s: s.start)
    return out


def direct_children(text, span):
    """回傳 span 底下深度 1 的子元素（不含孫節點）。"""
    res = []
    depth = 0
    pending = None
    for m in iter_tags(text, span.inner_start, span.inner_end):
        closing, name, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            depth -= 1
            if depth == 0 and pending is not None:
                res.append(Span(pending[0], pending[1], pending[2],
                                m.start(), m.end(), pending[3]))
                pending = None
            elif depth < 0:
                depth = 0
        elif selfclose:
            if depth == 0:
                res.append(Span(name, m.start(), m.end(), m.end(), m.end(), attrs))
        else:
            if depth == 0:
                pending = (name, m.start(), m.end(), attrs)
            depth += 1
    return res


def child(text, span, name, children=None):
    """取得第一個指定名稱的直屬子元素，找不到回傳 None。"""
    for c in (children if children is not None else direct_children(text, span)):
        if c.name == name:
            return c
    return None


def child_text(text, span, name, children=None, default=''):
    c = child(text, span, name, children)
    if c is None:
        return default
    return text[c.inner_start:c.inner_end]


def apply_edits(text, edits):
    """套用 [(start, end, 新字串), ...]；區間不得重疊。"""
    edits = sorted(edits, key=lambda e: (e[0], e[1]))
    last = -1
    for s, e, _ in edits:
        if s < last:
            raise ValueError('替換區間重疊，已中止以免破壞檔案結構')
        last = e
    out = []
    pos = 0
    for s, e, new in edits:
        out.append(text[pos:s])
        out.append(new)
        pos = e
    out.append(text[pos:])
    return ''.join(out)


def xml_unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'")
             .replace('&amp;', '&'))


def xml_escape(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;')
             .replace("'", '&apos;'))
