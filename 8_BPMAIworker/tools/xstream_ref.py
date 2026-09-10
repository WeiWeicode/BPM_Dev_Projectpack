# -*- coding: utf-8 -*-
"""在 1_xml_tool/core/xml_utils 之上建一棵唯讀的節點樹，用來解析 XStream 的
XPATH 相對參照（reference="../../xxx/yyy[2]"）並就地展開。

只做兩件事：
  1. resolve(node, path) -> 目標節點
  2. inline_refs(text, 判斷式) -> 把符合條件的 reference 展開成實體內容

不重新序列化，全部走字串區間替換。
"""
import re
import sys

import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '1_xml_tool'))
from core import xml_utils as X

_REF_RE = re.compile(r'reference="([^"]*)"')


class Node(object):
    def __init__(self, span, parent):
        self.span = span
        self.name = span.name
        self.parent = parent
        self.children = []

    # XStream 路徑用單底線的真實類別名，檔案標籤名是雙底線
    @property
    def path_name(self):
        return self.name.replace('__', '_')

    @property
    def ref(self):
        m = _REF_RE.search(self.span.attrs or '')
        return m.group(1) if m else None

    def inner(self, text):
        return text[self.span.inner_start:self.span.inner_end]

    def raw(self, text):
        return text[self.span.start:self.span.end]

    def __repr__(self):
        return '<%s @%d>' % (self.name, self.span.start)


def build(text):
    """回傳 (root, 全部節點清單)。"""
    root_span = X.find_blocks(text, lambda n: True)[0]
    # find_blocks 已排序，但巢狀關係要自己接；改用遞迴 direct_children 較穩
    root = Node(root_span, None)
    all_nodes = [root]

    stack = [root]
    while stack:
        cur = stack.pop()
        for cs in X.direct_children(text, cur.span):
            n = Node(cs, cur)
            cur.children.append(n)
            all_nodes.append(n)
            stack.append(n)
    return root, all_nodes


_SEG_RE = re.compile(r'^(.+?)(?:\[(\d+)\])?$')


def resolve(node, path):
    """依 XStream 的相對路徑找目標節點；找不到回傳 None。"""
    cur = node
    for seg in path.split('/'):
        if seg == '..':
            cur = cur.parent
            if cur is None:
                return None
            continue
        m = _SEG_RE.match(seg)
        name, idx = m.group(1), int(m.group(2) or 1)
        hit = [c for c in cur.children if c.path_name == name]
        if len(hit) < idx:
            return None
        cur = hit[idx - 1]
    return cur


def is_pure_ancestor(path):
    return all(seg == '..' for seg in path.split('/'))


def inline_refs(text, should_inline):
    """把 should_inline(path) 為真的 reference 展開成目標節點的實體內容。

    回傳 (新文字, 展開筆數, 略過清單)。目標本身若還含 reference 就不展開，
    列進略過清單由人判斷 —— 靜默略過會產生看似正常但語意錯誤的檔案。
    """
    root, nodes = build(text)
    edits = []
    skipped = []
    done = 0
    for n in nodes:
        p = n.ref
        if p is None or not should_inline(p):
            continue
        target = resolve(n, p)
        if target is None:
            skipped.append((n.name, p, '路徑解析不到'))
            continue
        inner = target.inner(text)
        if 'reference="' in inner:
            skipped.append((n.name, p, '目標內含巢狀 reference'))
            continue
        edits.append((n.span.start, n.span.end,
                      '<%s>%s</%s>' % (n.name, inner, n.name)))
        done += 1
    return X.apply_edits(text, edits), done, skipped
