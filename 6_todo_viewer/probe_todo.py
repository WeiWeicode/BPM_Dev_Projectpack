# -*- coding: utf-8 -*-
"""P0 驗證腳本：釘死待辦的資料來源與狀態語意。

為什麼需要這支：直覺會以為「待辦 = WorkItem.performerOID 是我且未完成」，
但 performerOID 只在關卡**完成後**才寫入（記錄實際執行者），未完成的工作項目
該欄是 NULL —— 靠它查待辦會得到空清單。實際的待辦收件匣是 LocalToDoWorkItem。

本腳本把這個結論連同狀態語意一起重跑驗證，結論寫在 docs/待辦狀態語意.md。
一律唯讀，只跑 SELECT。SOAP 部分只打 191 測試區的唯讀方法 fetchWorkItemCount。

用法：
    python probe_todo.py            # 全部檢查
    python probe_todo.py --no-soap  # 只跑 SQL，不做 SOAP 交叉驗證
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DB_EXPLORER_DIR = os.path.join(REPO_ROOT, '3_db_explorer')
WS_EXPLORER_DIR = os.path.join(REPO_ROOT, '5_ws_explorer')

for path in (DB_EXPLORER_DIR, WS_EXPLORER_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# Windows 主控台預設是 Big5，直接印繁體中文會變亂碼
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from bpm_kb.db import Database

# 交叉驗證用的取樣使用者：待辦筆數多寡與狀態組合都不同，涵蓋 0/1/97 三種
SAMPLE_USERS = ['S090005', 'S017041', 'YS086004', 'S087003', 'S093012', 'S094009']

# 系統代理帳號，不存在於 Users 表；待辦表裡有它的資料是正常的
AUTO_AGENT_OID = '0000000000000000000AutoAgent0001'


def _title(text):
    print()
    print('=' * 70)
    print(text)
    print('=' * 70)


def _rows(rows):
    for row in rows:
        print('  ', row)


def check_performer_is_null(db):
    """U1 前提：未完成的 WorkItem 其 performerOID 為 NULL，不能用來查待辦。"""
    _title('1. performerOID 只在完成後才有值')
    open_total = db.scalar('''
        SELECT COUNT(*) FROM WorkItem WI
        JOIN ProcessInstance PI ON WI.contextOID = PI.contextOID
        WHERE WI.currentState IN (0, 1, 2) AND PI.currentState = 1''')
    open_named = db.scalar('''
        SELECT COUNT(*) FROM WorkItem WI
        JOIN ProcessInstance PI ON WI.contextOID = PI.contextOID
        JOIN Users U ON WI.performerOID = U.OID
        WHERE WI.currentState IN (0, 1, 2) AND PI.currentState = 1''')
    done_total = db.scalar('SELECT COUNT(*) FROM WorkItem WHERE currentState = 3')
    done_named = db.scalar('''
        SELECT COUNT(*) FROM WorkItem WI
        JOIN Users U ON WI.performerOID = U.OID
        WHERE WI.currentState = 3''')
    print('   未完成工作項目 %d 筆，其中 performerOID 對得到 Users 的只有 %d 筆'
          % (open_total, open_named))
    print('   已完成工作項目 %d 筆，其中 performerOID 對得到 Users 的有 %d 筆'
          % (done_total, done_named))
    return open_named


def check_todo_source(db):
    """LocalToDoWorkItem 才是待辦收件匣。"""
    _title('2. LocalToDoWorkItem 的形狀')
    total = db.scalar('SELECT COUNT(*) FROM LocalToDoWorkItem')
    distinct_wi = db.scalar('SELECT COUNT(DISTINCT workItemOID) FROM LocalToDoWorkItem')
    matched_user = db.scalar('''
        SELECT COUNT(*) FROM LocalToDoWorkItem T JOIN Users U ON T.userOID = U.OID''')
    matched_wi = db.scalar('''
        SELECT COUNT(*) FROM LocalToDoWorkItem T JOIN WorkItem W ON T.workItemOID = W.OID''')
    agent = db.scalar('SELECT COUNT(*) FROM LocalToDoWorkItem WHERE userOID = ?',
                      (AUTO_AGENT_OID,))
    print('   總筆數 %d，去重後工作項目 %d 個 —— 同一關卡可同時派給多人'
          % (total, distinct_wi))
    print('   userOID 對得到 Users：%d 筆；workItemOID 對得到 WorkItem：%d 筆'
          % (matched_user, matched_wi))
    print('   userOID 是系統代理 %s 的：%d 筆（非真人，查詢時自然被排除）'
          % (AUTO_AGENT_OID, agent))

    _title('3. 待辦對應的 WorkItem.currentState 分布')
    _rows(db.query('''
        SELECT W.currentState AS 狀態, COUNT(*) AS 筆數
        FROM LocalToDoWorkItem T JOIN WorkItem W ON T.workItemOID = W.OID
        GROUP BY W.currentState ORDER BY W.currentState'''))


def check_state_semantics(db, use_soap):
    """U1：用 SOAP 的 fetchWorkItemCount 反推哪些 currentState 算待辦。"""
    _title('4. 狀態語意交叉驗證（SQL 對 SOAP）')
    service = None
    if use_soap:
        try:
            from ws_client import WorkflowService
            service = WorkflowService()
        except Exception as exc:
            print('   SOAP 客戶端載入失敗，略過交叉驗證：%s' % exc)

    print('   %-10s %-28s %8s %8s %6s' % ('使用者', 'SQL 各狀態筆數', 'SQL(0,1)', 'SOAP', '一致'))
    for user_id in SAMPLE_USERS:
        rows = db.query('''
            SELECT W.currentState AS st, COUNT(*) AS c
            FROM LocalToDoWorkItem T
            JOIN Users U ON T.userOID = U.OID
            JOIN WorkItem W ON T.workItemOID = W.OID
            WHERE U.id = ? GROUP BY W.currentState ORDER BY W.currentState''', (user_id,))
        detail = ' '.join('%s:%s' % (r['st'], r['c']) for r in rows)
        sql_count = sum(r['c'] for r in rows if r['st'] in (0, 1))
        soap_count = '-'
        agree = '-'
        if service is not None:
            try:
                soap_count = service.call('fetchWorkItemCount', pUserID=user_id,
                                          pAccessCondition=0, pViewTimesType='0')
                agree = 'OK' if int(soap_count) == sql_count else '**不符**'
            except Exception as exc:
                soap_count = '錯誤:%s' % exc
        print('   %-10s %-28s %8d %8s %6s'
              % (user_id, detail, sql_count, soap_count, agree))
    print()
    print('   判讀：SOAP 的待辦數 = SQL 中 currentState 為 0 或 1 的筆數，')
    print('         狀態 3（已完成）、4（流程撤銷）、97 皆不計入。')


def check_abnormal_states(db):
    """U2：currentState = 97 是什麼。"""
    _title('5. currentState = 97 的資料')
    _rows(db.query('''
        SELECT W.OID, W.workItemName, W.dispatchType, W.signoffState,
               W.createdTime, W.completedTime, PI.serialNumber, PI.currentState AS 流程狀態
        FROM WorkItem W LEFT JOIN ProcessInstance PI ON W.contextOID = PI.contextOID
        WHERE W.currentState = 97'''))
    print('   兩筆皆 signoffState = 1、completedTime 為 NULL、流程仍在進行中，')
    print('   但 SOAP 的待辦數不計入 —— 視為卡住的異常關卡，清單中排除但可另行標記。')


def check_delegation(db):
    """U4：代理簽核欄位在待辦裡是否有值。"""
    _title('6. 代理相關欄位')
    print('   待辦中 bypassPerformerOID 有值：%d 筆'
          % db.scalar('''SELECT COUNT(*) FROM LocalToDoWorkItem T
                         JOIN WorkItem W ON T.workItemOID = W.OID
                         WHERE W.bypassPerformerOID IS NOT NULL'''))
    print('   待辦中 ownerOID 有值：%d 筆'
          % db.scalar('''SELECT COUNT(*) FROM LocalToDoWorkItem T
                         JOIN WorkItem W ON T.workItemOID = W.OID
                         WHERE W.ownerOID IS NOT NULL'''))
    print('   全表 bypassPerformerOID 有值：%d 筆'
          % db.scalar('SELECT COUNT(*) FROM WorkItem WHERE bypassPerformerOID IS NOT NULL'))
    print('   判讀：待辦集合中 bypassPerformerOID 全為 NULL，')
    print('         代理是「完成時」才落地的資訊，不影響待辦清單的查法。')


def check_three_lists(db, user_id='S094009'):
    """三類清單各自跑一次，確認查得出東西。"""
    _title('7. 三類清單試查（%s）' % user_id)

    print('   [待簽核]')
    _rows(db.query('''
        SELECT TOP 5 W.OID AS workItemOID, W.workItemName AS 關卡,
               PI.serialNumber AS 單號, PI.processInstanceName AS 流程,
               W.currentState AS 關卡狀態, T.createdTime AS 派送時間
        FROM LocalToDoWorkItem T
        JOIN Users U ON T.userOID = U.OID
        JOIN WorkItem W ON T.workItemOID = W.OID
        LEFT JOIN ProcessInstance PI ON W.contextOID = PI.contextOID
        WHERE U.id = ? AND W.currentState IN (0, 1)
        ORDER BY T.createdTime DESC''', (user_id,)))

    print('   [我申請的] 依流程狀態統計')
    _rows(db.query('''
        SELECT PI.currentState AS 流程狀態, COUNT(*) AS 筆數
        FROM ProcessInstance PI JOIN Users U ON PI.requesterOID = U.OID
        WHERE U.id = ? GROUP BY PI.currentState ORDER BY PI.currentState''', (user_id,)))

    print('   [我經辦過的] 總數')
    print('   ', db.scalar('''
        SELECT COUNT(*) FROM WorkItem W JOIN Users U ON W.performerOID = U.OID
        WHERE U.id = ? AND W.currentState = 3''', (user_id,)))


def main():
    use_soap = '--no-soap' not in sys.argv
    with Database() as db:
        check_performer_is_null(db)
        check_todo_source(db)
        check_state_semantics(db, use_soap)
        check_abnormal_states(db)
        check_delegation(db)
        check_three_lists(db)
    print()
    print('完成。結論見 docs/待辦狀態語意.md')


if __name__ == '__main__':
    main()
