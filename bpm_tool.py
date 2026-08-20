# -*- coding: utf-8 -*-
"""鼎新 BPM XML 雙向處理工具 — 終端互動主程式。

    python bpm_tool.py                  互動選單
    python bpm_tool.py export <檔案>    直接匯出 JSON
    python bpm_tool.py write <JSON> [原始XML]   直接回寫
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import bpmn_handler, form_handler  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PREFIX = '已完成_'
LINE = '=' * 60


def _setup_console():
    """讓 Windows 終端機也能正常輸出中文與符號。"""
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            try:
                setattr(sys, stream_name,
                        io.TextIOWrapper(stream.buffer, encoding='utf-8',
                                         errors='replace', line_buffering=True))
            except Exception:
                pass


OK = '✔'
NG = '✘'


def _ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return '0'


def _list_files(extensions):
    names = []
    for name in sorted(os.listdir(BASE_DIR)):
        if not os.path.isfile(os.path.join(BASE_DIR, name)):
            continue
        if name.startswith(OUTPUT_PREFIX):
            continue
        if os.path.splitext(name)[1].lower() in extensions:
            names.append(name)
    return names


def _kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.form':
        return 'FORM'
    if ext == '.bpmn':
        return 'BPMN'
    return None


# ---------------------------------------------------------------- 匯出

def do_export(path):
    kind = _kind_of(path)
    if kind is None:
        print('%s 不支援的副檔名：%s' % (NG, path))
        return False

    name = os.path.basename(path)
    print('正在解析 %s...' % name)
    if kind == 'FORM':
        data = form_handler.extract(path)
        count = len(data['fields'])
        detail = '%s 成功萃取 %d 個欄位 (已排除 JavaScript 與樣式)' % (OK, count)
    else:
        data = bpmn_handler.extract(path)
        count = len(data['activities'])
        perms = sum(len(a['buttons']) + len(a['fieldPermissions'])
                    for a in data['activities'])
        detail = '%s 成功萃取 %d 個關卡、%d 筆按鈕/欄位權限' % (OK, count, perms)

    out_path = os.path.join(BASE_DIR, os.path.splitext(name)[0] + '.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(detail)
    print('%s 已產出 JSON 檔案: %s' % (OK, os.path.basename(out_path)))
    return True


def menu_export():
    files = _list_files({'.form', '.bpmn'})
    if not files:
        print('%s 目錄下找不到 .form 或 .bpmn 檔案。' % NG)
        return

    print('\n>>> 搜尋目錄下支援的 XML 檔案...')
    for i, name in enumerate(files, 1):
        tag = '表單' if _kind_of(name) == 'FORM' else '流程'
        print(' [%d] %s (%s)' % (i, name, tag))
    print(' [A] 全部轉換')
    print(' [0] 返回主選單')

    choice = _ask('\n請選擇要匯出的檔案: ').upper()
    if choice in ('0', ''):
        return
    targets = files if choice == 'A' else None
    if targets is None:
        if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
            print('%s 輸入無效。' % NG)
            return
        targets = [files[int(choice) - 1]]

    print()
    for name in targets:
        try:
            do_export(os.path.join(BASE_DIR, name))
        except Exception as exc:  # noqa: BLE001
            print('%s 匯出失敗 (%s)：%s' % (NG, name, exc))
        print()


# ---------------------------------------------------------------- 回寫

def do_write_back(json_path, xml_path=None):
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    file_type = config.get('fileType')
    if file_type not in ('FORM', 'BPMN'):
        print('%s JSON 缺少有效的 fileType（需為 FORM 或 BPMN）。' % NG)
        return 'failed'

    if xml_path is None:
        source = config.get('sourceFile') or ''
        xml_path = os.path.join(BASE_DIR, source)
    if not os.path.isfile(xml_path):
        print('%s 找不到原始 XML 檔案：%s' % (NG, xml_path))
        return 'failed'

    out_name = OUTPUT_PREFIX + os.path.basename(xml_path)
    out_path = os.path.join(os.path.dirname(os.path.abspath(xml_path)), out_name)
    if os.path.exists(out_path):
        if _ask('檔案「%s」已存在，要覆蓋嗎？(y/N): ' % out_name).lower() != 'y':
            print('已取消。')
            return 'failed'

    print('正在以「originalId」為鍵值進行比對與 ID 替換...')
    try:
        if file_type == 'FORM':
            changed, messages = form_handler.write_back(xml_path, config, out_path)
            summary = '%s 成功比對並更新 %d 個欄位 ID' % (OK, changed)
        else:
            changed, fields, messages = bpmn_handler.write_back(xml_path, config, out_path)
            summary = ('%s 成功比對並更新 %d 個關卡 ID、%d 個欄位/按鈕 ID'
                       % (OK, changed, fields))
    except ValueError as exc:
        print('%s 回寫中止：%s' % (NG, exc))
        print('  原始檔案未受影響，也未產生任何輸出檔。')
        return 'failed'

    for msg in messages:
        print(msg)
    print(summary)

    if not os.path.exists(out_path):
        print('  JSON 中沒有任何 ID 被修改，未產生輸出檔。')
        return 'noop'
    print('%s 已生成新檔案: %s' % (OK, out_name))
    return 'written'


def menu_write_back():
    files = _list_files({'.json'})
    if not files:
        print('%s 目錄下找不到 .json 設定檔，請先執行功能 [1]。' % NG)
        return

    print('\n>>> 搜尋目錄下可用的 JSON 設定檔...')
    for i, name in enumerate(files, 1):
        print(' [%d] %s' % (i, name))
    print(' [0] 返回主選單')

    choice = _ask('\n請選擇要回寫的 JSON 設定檔: ')
    if choice in ('0', ''):
        return
    if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
        print('%s 輸入無效。' % NG)
        return

    json_path = os.path.join(BASE_DIR, files[int(choice) - 1])
    with open(json_path, 'r', encoding='utf-8') as f:
        default_source = json.load(f).get('sourceFile') or ''

    answer = _ask('請確認要回寫的原始 XML 檔案 [預設: %s]: ' % default_source)
    xml_name = answer or default_source
    xml_path = xml_name if os.path.isabs(xml_name) else os.path.join(BASE_DIR, xml_name)

    print()
    if do_write_back(json_path, xml_path) == 'written':
        print('\n' + LINE)
        print('更新成功！原始檔案未受影響。')
        print(LINE)


# ---------------------------------------------------------------- 主選單

def main_menu():
    while True:
        print('\n' + LINE)
        print('           鼎新 BPM XML 雙向處理工具 (Python)')
        print(LINE)
        print(' [1] 匯出 XML 轉 JSON (Extract)')
        print('     - 解析 .form / .bpmn 檔案，萃取 ID、中文名稱與按鈕權限')
        print(' [2] 匯入 JSON 回寫 XML (Write-back)')
        print('     - 依 originalId 鍵值更新 ID，另存為「已完成_檔名」')
        print(' [0] 離開系統')
        print(LINE)
        choice = _ask('請選擇功能項目 [0-2]: ')

        if choice == '1':
            menu_export()
        elif choice == '2':
            menu_write_back()
        elif choice == '0':
            print('再見。')
            return
        else:
            print('%s 請輸入 0、1 或 2。' % NG)


def main(argv):
    _setup_console()
    if not argv:
        main_menu()
        return 0

    command = argv[0].lower()
    if command == 'export' and len(argv) >= 2:
        return 0 if do_export(os.path.abspath(argv[1])) else 1
    if command == 'write' and len(argv) >= 2:
        xml = os.path.abspath(argv[2]) if len(argv) >= 3 else None
        return 0 if do_write_back(os.path.abspath(argv[1]), xml) != 'failed' else 1

    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
