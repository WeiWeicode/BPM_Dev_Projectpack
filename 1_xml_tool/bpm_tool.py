# -*- coding: utf-8 -*-
"""鼎新 BPM XML 雙向處理工具 — 終端互動主程式。

    python bpm_tool.py                  分層互動選單（專案 => 流程/表單 => 檔案 => 處理動作）
    python bpm_tool.py export <檔案>    直接匯出 JSON
    python bpm_tool.py write <JSON> [原始XML]   直接回寫欄位
    python bpm_tool.py export-js <表單> 直接匯出表單 JavaScript (.js)
    python bpm_tool.py write-js <JS> [目標表單] 直接回寫 JavaScript 至表單
"""

import io
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core import bpmn_handler, form_handler  # noqa: E402

# samples/ 作為專案根目錄，第二層為專案，第三層為流程/表單
BASE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'samples')
OUTPUT_PREFIX = '已完成_'
CATEGORIES = ['流程', '表單']
LINE = '=' * 60
OK = '✔'
NG = '✘'


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


def _ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return '0'


def _kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.form':
        return 'FORM'
    if ext == '.bpmn':
        return 'BPMN'
    if ext == '.json':
        return 'JSON'
    if ext == '.js':
        return 'JS'
    return None


def _list_files(target_dir, extensions, include_completed=False):
    """掃描指定目錄下符合副檔名的檔案，可指定是否包含已完成產出檔。"""
    if not os.path.isdir(target_dir):
        return []
    names = []
    for name in sorted(os.listdir(target_dir)):
        full_path = os.path.join(target_dir, name)
        if not os.path.isfile(full_path):
            continue
        if not include_completed and (name.startswith(OUTPUT_PREFIX) or name.startswith('已完成')):
            continue
        if os.path.splitext(name)[1].lower() in extensions:
            names.append(name)
    return names


def _list_projects():
    """掃描 samples/ 下的所有專案資料夾。"""
    if not os.path.isdir(BASE_DIR):
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
        except OSError:
            pass
        return []
    projects = []
    for name in sorted(os.listdir(BASE_DIR)):
        full_path = os.path.join(BASE_DIR, name)
        if os.path.isdir(full_path) and not name.startswith('.'):
            projects.append(name)
    return projects


# ---------------------------------------------------------------- 核心處理函式

def do_export(path):
    """匯出 XML (.form / .bpmn) 欄位/關卡為 JSON 設定檔，產出於同目錄。"""
    kind = _kind_of(path)
    if kind not in ('FORM', 'BPMN'):
        print('%s 不支援的副檔名：%s' % (NG, path))
        return False

    name = os.path.basename(path)
    target_dir = os.path.dirname(os.path.abspath(path))
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

    out_path = os.path.join(target_dir, os.path.splitext(name)[0] + '.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(detail)
    print('%s 已產出 JSON 檔案: %s' % (OK, os.path.basename(out_path)))
    return True


def do_export_script(path):
    """從 .form 檔案萃取 <script> 內容存為 .js 檔案。"""
    kind = _kind_of(path)
    if kind != 'FORM':
        print('%s 僅支援 .form 表單檔案萃取 JavaScript：%s' % (NG, path))
        return False

    name = os.path.basename(path)
    target_dir = os.path.dirname(os.path.abspath(path))
    print('正在從 %s 萃取 JavaScript 腳本...' % name)
    js_code, msg = form_handler.extract_script(path)
    if js_code is None:
        print('%s %s' % (NG, msg))
        return False

    out_name = os.path.splitext(name)[0] + '.js'
    out_path = os.path.join(target_dir, out_name)
    if os.path.exists(out_path):
        if _ask('檔案「%s」已存在，要覆蓋嗎？(y/N): ' % out_name).lower() != 'y':
            print('已取消。')
            return False

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(js_code)
        if not js_code.endswith('\n'):
            f.write('\n')

    print('%s %s' % (OK, msg))
    print('%s 已產出 JavaScript 檔案: %s' % (OK, out_name))
    return True


def do_write_back(json_path, xml_path=None):
    """將 JSON 設定檔回寫至 XML，產出「已完成_檔名」於同目錄。"""
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    file_type = config.get('fileType')
    if file_type not in ('FORM', 'BPMN'):
        print('%s JSON 缺少有效的 fileType（需為 FORM 或 BPMN）。' % NG)
        return 'failed'

    base_dir = os.path.dirname(os.path.abspath(json_path))
    if xml_path is None:
        source = config.get('sourceFile') or ''
        xml_path = os.path.join(base_dir, source)
    if not os.path.isfile(xml_path):
        print('%s 找不到原始 XML 檔案：%s' % (NG, xml_path))
        return 'failed'

    xml_basename = os.path.basename(xml_path)
    if xml_basename.startswith(OUTPUT_PREFIX) or xml_basename.startswith('已完成'):
        out_name = xml_basename
    else:
        out_name = OUTPUT_PREFIX + xml_basename
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


def do_write_back_script(js_path, form_path=None):
    """將 .js 檔案回寫導入至目標 .form 檔案的 <script> 區塊。"""
    base_dir = os.path.dirname(os.path.abspath(js_path))
    js_name = os.path.basename(js_path)

    if form_path is None:
        base_no_ext = os.path.splitext(js_name)[0]
        candidate_completed = os.path.join(base_dir, OUTPUT_PREFIX + base_no_ext + '.form')
        candidate_raw = os.path.join(base_dir, base_no_ext + '.form')
        if os.path.isfile(candidate_completed):
            form_path = candidate_completed
        elif os.path.isfile(candidate_raw):
            form_path = candidate_raw
        else:
            print('%s 找不到預設對應的表單檔案：%s' % (NG, candidate_raw))
            return 'failed'

    if not os.path.isfile(form_path):
        print('%s 找不到目標表單檔案：%s' % (NG, form_path))
        return 'failed'

    form_basename = os.path.basename(form_path)
    if form_basename.startswith(OUTPUT_PREFIX) or form_basename.startswith('已完成'):
        out_name = form_basename
    else:
        out_name = OUTPUT_PREFIX + form_basename
    out_path = os.path.join(os.path.dirname(os.path.abspath(form_path)), out_name)
    if os.path.exists(out_path):
        if _ask('檔案「%s」已存在，要覆蓋嗎？(y/N): ' % out_name).lower() != 'y':
            print('已取消。')
            return 'failed'

    with open(js_path, 'r', encoding='utf-8') as f:
        js_content = f.read()

    print('正在將 JavaScript 腳本寫入 %s 的 <script> 區塊...' % os.path.basename(form_path))
    try:
        form_handler.write_back_script(form_path, js_content, out_path)
    except Exception as exc:  # noqa: BLE001
        print('%s 回寫失敗：%s' % (NG, exc))
        return 'failed'

    print('%s 成功更新表單 JavaScript 腳本！' % OK)
    print('%s 已生成新檔案: %s' % (OK, out_name))
    return 'written'


# ---------------------------------------------------------------- 動作與選單

def _action_on_xml(xml_path, target_dir):
    """針對 XML 檔案 (.form / .bpmn) 的處理選單。"""
    xml_name = os.path.basename(xml_path)
    kind = _kind_of(xml_name)
    is_form = (kind == 'FORM')
    tag = '表單 XML' if is_form else '流程 XML'

    while True:
        print('\n' + LINE)
        print('目標檔案：%s (%s)' % (xml_name, tag))
        print(LINE)

        if is_form:
            print(' [1] 匯出欄位清單轉 JSON (Extract Fields)')
            print(' [2] 匯出 JavaScript 腳本存為 .js (Extract JS)')
            print(' [3] 匯入 JSON 回寫欄位到此 XML (Write-back Fields)')
            print(' [4] 匯入 .js 回寫腳本到此 XML (Write-back JS)')
            print(' [0] 返回檔案清單')
            print(LINE)
            action = _ask('請選擇處理動作 [0-4]: ')
        else:
            print(' [1] 匯出關卡與權限轉 JSON (Extract)')
            print(' [2] 匯入 JSON 回寫到此 XML (Write-back)')
            print(' [0] 返回檔案清單')
            print(LINE)
            action = _ask('請選擇處理動作 [0-2]: ')

        if action == '0':
            return

        if action == '1':
            print()
            try:
                do_export(xml_path)
            except Exception as exc:  # noqa: BLE001
                print('%s 匯出失敗 (%s)：%s' % (NG, xml_name, exc))
            _ask('\n請按 Enter 鍵繼續...')
            return

        elif is_form and action == '2':
            print()
            try:
                do_export_script(xml_path)
            except Exception as exc:  # noqa: BLE001
                print('%s 萃取腳本失敗 (%s)：%s' % (NG, xml_name, exc))
            _ask('\n請按 Enter 鍵繼續...')
            return

        elif (not is_form and action == '2') or (is_form and action == '3'):
            json_files = _list_files(target_dir, {'.json'})
            if not json_files:
                print('%s 同目錄下找不到 .json 設定檔，請先執行匯出。' % NG)
                _ask('\n請按 Enter 鍵繼續...')
                continue

            base_no_ext = os.path.splitext(xml_name)[0]
            default_json = base_no_ext + '.json'
            default_idx = None

            print('\n可用 JSON 設定檔：')
            for idx, jname in enumerate(json_files, 1):
                mark = ' (推薦)' if jname == default_json else ''
                if jname == default_json:
                    default_idx = idx
                print(' [%d] %s%s' % (idx, jname, mark))
            print(' [0] 取消')

            prompt = '請選擇要套用的 JSON 設定檔'
            if default_idx is not None:
                prompt += ' [預設: %d]' % default_idx
            prompt += ': '

            c = _ask(prompt)
            if c == '0':
                continue
            if not c and default_idx is not None:
                chosen_json = json_files[default_idx - 1]
            elif c.isdigit() and 1 <= int(c) <= len(json_files):
                chosen_json = json_files[int(c) - 1]
            else:
                print('%s 選擇無效。' % NG)
                continue

            print()
            json_full_path = os.path.join(target_dir, chosen_json)
            res = do_write_back(json_full_path, xml_path)
            if res == 'written':
                print('\n' + LINE)
                print('更新成功！原始檔案未受影響。')
                print(LINE)
            _ask('\n請按 Enter 鍵繼續...')
            return

        elif is_form and action == '4':
            js_files = _list_files(target_dir, {'.js'})
            if not js_files:
                print('%s 同目錄下找不到 .js 腳本檔案。' % NG)
                _ask('\n請按 Enter 鍵繼續...')
                continue

            base_no_ext = os.path.splitext(xml_name)[0]
            default_js = base_no_ext + '.js'
            default_idx = None

            print('\n可用 JavaScript 檔案：')
            for idx, jname in enumerate(js_files, 1):
                mark = ' (推薦)' if jname == default_js else ''
                if jname == default_js:
                    default_idx = idx
                print(' [%d] %s%s' % (idx, jname, mark))
            print(' [0] 取消')

            prompt = '請選擇要回寫的 JavaScript 檔案'
            if default_idx is not None:
                prompt += ' [預設: %d]' % default_idx
            prompt += ': '

            c = _ask(prompt)
            if c == '0':
                continue
            if not c and default_idx is not None:
                chosen_js = js_files[default_idx - 1]
            elif c.isdigit() and 1 <= int(c) <= len(js_files):
                chosen_js = js_files[int(c) - 1]
            else:
                print('%s 選擇無效。' % NG)
                continue

            print()
            js_full_path = os.path.join(target_dir, chosen_js)
            res = do_write_back_script(js_full_path, xml_path)
            if res == 'written':
                print('\n' + LINE)
                print('更新成功！原始檔案未受影響。')
                print(LINE)
            _ask('\n請按 Enter 鍵繼續...')
            return

        else:
            print('%s 請輸入有效選項。' % NG)


def _action_on_js(js_path, target_dir):
    """針對 JavaScript 檔案 (.js) 的處理選單。"""
    js_name = os.path.basename(js_path)

    while True:
        print('\n' + LINE)
        print('目標檔案：%s (JavaScript 腳本)' % js_name)
        print(LINE)
        print(' [1] 匯入此 JS 回寫至表單 XML (Write-back to .form)')
        print(' [0] 返回檔案清單')
        print(LINE)
        action = _ask('請選擇處理動作 [0-1]: ')

        if action == '1':
            form_files = _list_files(target_dir, {'.form'}, include_completed=True)
            if not form_files:
                print('%s 同目錄下找不到可導入的 .form 表單檔案。' % NG)
                _ask('\n請按 Enter 鍵繼續...')
                continue

            base_no_ext = os.path.splitext(js_name)[0]
            completed_form = OUTPUT_PREFIX + base_no_ext + '.form'
            raw_form = base_no_ext + '.form'
            if completed_form in form_files:
                default_form = completed_form
            elif raw_form in form_files:
                default_form = raw_form
            else:
                default_form = None
            default_idx = None

            print('\n請選擇要導入的表單 XML 檔案：')
            for idx, fname in enumerate(form_files, 1):
                mark = ' (推薦)' if fname == default_form else ''
                if fname == default_form:
                    default_idx = idx
                print(' [%d] %s%s' % (idx, fname, mark))
            print(' [0] 取消')

            prompt = '請選擇表單檔案'
            if default_idx is not None:
                prompt += ' [預設: %d]' % default_idx
            prompt += ': '

            c = _ask(prompt)
            if c == '0':
                continue
            if not c and default_idx is not None:
                chosen_form = form_files[default_idx - 1]
            elif c.isdigit() and 1 <= int(c) <= len(form_files):
                chosen_form = form_files[int(c) - 1]
            else:
                print('%s 選擇無效。' % NG)
                continue

            print()
            form_full_path = os.path.join(target_dir, chosen_form)
            res = do_write_back_script(js_path, form_full_path)
            if res == 'written':
                print('\n' + LINE)
                print('更新成功！原始檔案未受影響。')
                print(LINE)
            _ask('\n請按 Enter 鍵繼續...')
            return
        elif action == '0':
            return
        else:
            print('%s 請輸入 0 或 1。' % NG)


def _action_on_json(json_path, target_dir):
    """針對 JSON 設定檔的處理選單。"""
    json_name = os.path.basename(json_path)

    while True:
        print('\n' + LINE)
        print('目標檔案：%s (設定檔 JSON)' % json_name)
        print(LINE)
        print(' [1] 匯入此 JSON 回寫 XML (Write-back)')
        print(' [0] 返回檔案清單')
        print(LINE)
        action = _ask('請選擇處理動作 [0-1]: ')

        if action == '1':
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as exc:  # noqa: BLE001
                print('%s 無法讀取 JSON 內容：%s' % (NG, exc))
                _ask('\n請按 Enter 鍵繼續...')
                return

            file_type = config.get('fileType')
            default_source = config.get('sourceFile') or ''
            xml_files = _list_files(target_dir, {'.form', '.bpmn'}, include_completed=True)

            if not xml_files:
                print('%s 同目錄下找不到可回寫的 .form 或 .bpmn 檔案。' % NG)
                _ask('\n請按 Enter 鍵繼續...')
                continue

            default_idx = None
            base_no_ext = os.path.splitext(json_name)[0]
            completed_source = OUTPUT_PREFIX + default_source if default_source else ''
            completed_base = OUTPUT_PREFIX + base_no_ext
            default_xml = None
            for candidate_name in (completed_source, default_source, completed_base + '.form', completed_base + '.bpmn', base_no_ext + '.form', base_no_ext + '.bpmn'):
                if candidate_name and candidate_name in xml_files:
                    default_xml = candidate_name
                    break

            print('\n可用 XML 檔案：')
            for idx, xname in enumerate(xml_files, 1):
                xtag = '表單' if _kind_of(xname) == 'FORM' else '流程'
                mark = ''
                if default_xml and xname == default_xml:
                    mark = ' (推薦)'
                    default_idx = idx
                print(' [%d] %s (%s)%s' % (idx, xname, xtag, mark))
            print(' [0] 取消')

            prompt = '請選擇要回寫的 XML 檔案'
            if default_idx is not None:
                prompt += ' [預設: %d]' % default_idx
            prompt += ': '

            c = _ask(prompt)
            if c == '0':
                continue
            if not c and default_idx is not None:
                chosen_xml = xml_files[default_idx - 1]
            elif c.isdigit() and 1 <= int(c) <= len(xml_files):
                chosen_xml = xml_files[int(c) - 1]
            else:
                print('%s 選擇無效。' % NG)
                continue

            print()
            xml_full_path = os.path.join(target_dir, chosen_xml)
            res = do_write_back(json_path, xml_full_path)
            if res == 'written':
                print('\n' + LINE)
                print('更新成功！原始檔案未受影響。')
                print(LINE)
            _ask('\n請按 Enter 鍵繼續...')
            return
        elif action == '0':
            return
        else:
            print('%s 請輸入 0 或 1。' % NG)


def _batch_export_xml(target_dir, xml_files):
    """批次匯出目錄下所有 XML 檔案為 JSON。"""
    print('\n>>> 開始批次匯出 %d 個檔案...' % len(xml_files))
    success_count = 0
    for name in xml_files:
        full_path = os.path.join(target_dir, name)
        try:
            if do_export(full_path):
                success_count += 1
        except Exception as exc:  # noqa: BLE001
            print('%s 匯出失敗 (%s)：%s' % (NG, name, exc))
        print()
    print('%s 批次匯出完成：%d/%d 成功。' % (OK, success_count, len(xml_files)))
    _ask('\n請按 Enter 鍵繼續...')


def menu_select_file(project_name, category_name, target_dir):
    """第三層：選擇檔案。"""
    while True:
        files = _list_files(target_dir, {'.form', '.bpmn', '.json', '.js'})
        xml_files = [f for f in files if _kind_of(f) in ('FORM', 'BPMN')]

        rel_path = os.path.relpath(target_dir, SCRIPT_DIR)
        print('\n' + LINE)
        print('專案：%s > %s' % (project_name, category_name))
        print('路徑：%s' % rel_path)
        print(LINE)

        if not files:
            print('%s 此目錄下暫無可用檔案。' % NG)
            print('  請將 .form / .bpmn 檔案放入上述資料夾後再試。')
            print(LINE)
            _ask('請按 Enter 鍵返回上一層...')
            return

        print('可用檔案清單：')
        for i, name in enumerate(files, 1):
            kind = _kind_of(name)
            if kind == 'FORM':
                tag = '表單 XML'
            elif kind == 'BPMN':
                tag = '流程 XML'
            elif kind == 'JSON':
                tag = '設定檔 JSON'
            else:
                tag = 'JavaScript 腳本'
            print(' [%d] %s (%s)' % (i, name, tag))

        if xml_files:
            print(' [A] 全部 XML 批次匯出欄位 JSON (%d 個檔案)' % len(xml_files))
        print(' [0] 返回上一層（重選類別）')
        print(LINE)

        choice = _ask('請選擇要處理的檔案: ').upper()
        if choice in ('0', ''):
            return

        if choice == 'A' and xml_files:
            _batch_export_xml(target_dir, xml_files)
            continue

        if not choice.isdigit() or not (1 <= int(choice) <= len(files)):
            print('%s 輸入無效。' % NG)
            continue

        chosen_file = files[int(choice) - 1]
        file_path = os.path.join(target_dir, chosen_file)
        kind = _kind_of(chosen_file)

        if kind in ('FORM', 'BPMN'):
            _action_on_xml(file_path, target_dir)
        elif kind == 'JSON':
            _action_on_json(file_path, target_dir)
        elif kind == 'JS':
            _action_on_js(file_path, target_dir)


def menu_select_category(project_name):
    """第二層：選擇流程或表單。"""
    project_dir = os.path.join(BASE_DIR, project_name)

    while True:
        print('\n' + LINE)
        print('專案：%s' % project_name)
        print(LINE)
        print('請選擇類別：')
        for i, cat in enumerate(CATEGORIES, 1):
            print(' [%d] %s' % (i, cat))
        print(' [0] 返回上一層（重選專案）')
        print(LINE)

        choice = _ask('請選擇類別 [0-%d]: ' % len(CATEGORIES))
        if choice in ('0', ''):
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(CATEGORIES)):
            print('%s 輸入無效。' % NG)
            continue

        category_name = CATEGORIES[int(choice) - 1]
        target_dir = os.path.join(project_dir, category_name)
        os.makedirs(target_dir, exist_ok=True)

        menu_select_file(project_name, category_name, target_dir)


def main_menu():
    """第一層：選擇專案。"""
    while True:
        projects = _list_projects()

        print('\n' + LINE)
        print('           鼎新 BPM XML 雙向處理工具 (Python)')
        print(LINE)

        if not projects:
            print('%s 目前 samples/ 目錄下尚無任何專案資料夾。' % NG)
            print('  請在 samples/ 下建立專案資料夾（例如 samples/快速開發測試）。')
            print(LINE)
            print(' [0] 離開系統')
            print(LINE)
            _ask('請按 Enter 鍵離開...')
            return

        print('請選擇專案：')
        for i, name in enumerate(projects, 1):
            print(' [%d] %s' % (i, name))
        print(' [0] 離開系統')
        print(LINE)

        choice = _ask('請選擇專案 [0-%d]: ' % len(projects))
        if choice in ('0', ''):
            print('再見。')
            return

        if not choice.isdigit() or not (1 <= int(choice) <= len(projects)):
            print('%s 請輸入 0 到 %d 的數字。' % (NG, len(projects)))
            continue

        project_name = projects[int(choice) - 1]
        menu_select_category(project_name)


def main(argv):
    _setup_console()
    if not argv:
        main_menu()
        return 0

    command = argv[0].lower()
    if command == 'export' and len(argv) >= 2:
        return 0 if do_export(os.path.abspath(argv[1])) else 1
    if command == 'export-js' and len(argv) >= 2:
        return 0 if do_export_script(os.path.abspath(argv[1])) else 1
    if command == 'write' and len(argv) >= 2:
        xml = os.path.abspath(argv[2]) if len(argv) >= 3 else None
        return 0 if do_write_back(os.path.abspath(argv[1]), xml) != 'failed' else 1
    if command == 'write-js' and len(argv) >= 2:
        form = os.path.abspath(argv[2]) if len(argv) >= 3 else None
        return 0 if do_write_back_script(os.path.abspath(argv[1]), form) != 'failed' else 1

    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
