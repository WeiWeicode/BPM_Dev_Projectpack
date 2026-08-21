// 從 index.html 抽出 CORE 區塊，用真實 .bpmn / .form 驗證解析與無損回寫。
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.dirname(decodeURIComponent(new URL(import.meta.url).pathname).replace(/^\/(?=[A-Za-z]:)/, ''));
// 範例檔集中在 repo 根目錄的 samples/，與 1_xml_tool 共用
const SAMPLES = path.join(DIR, '..', 'samples');

// 範例檔改名時只需改這裡
const SAMPLE = {
  bpmnWithPerm: '已完成匯入_測試快速開發-欄位權限.bpmn',  // 已設權限，引用 quickDevTestFormImport
  formRenamed:  '已完成匯入_quickDevTestForm.form',      // 已套用命名規範的表單
  bpmnOriginal: '原檔案-測試快速開發.bpmn',                // 設計師原始匯出
  formOriginal: '原檔案-quickDevTestForm.form',           // 未改 ID 的表單
};
const html = fs.readFileSync(path.join(DIR, 'index.html'), 'utf8');
const core = html.split('// ==== CORE START ====')[1].split('// ==== CORE END ====')[0];
const Core = new Function(core + '\nreturn Core;')();

const readXml = (f) => {
  let b = fs.readFileSync(path.join(SAMPLES, f));
  let bom = false;
  if (b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf) { bom = true; b = b.subarray(3); }
  return { text: b.toString('utf8'), bom };
};

let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) { pass++; console.log('  ✔ ' + msg); } else { fail++; console.log('  ✘ ' + msg); } };
const eq = (a, b, msg) => ok(a === b, msg + (a === b ? '' : `\n      實得: ${JSON.stringify(a)}\n      預期: ${JSON.stringify(b)}`));

// ---------------------------------------------------------------- 1. BPMN 解析
console.log('\n[1] BPMN 解析');
const src = readXml(SAMPLE.bpmnWithPerm);
const bpmn = Core.parseBpmn(src.text, SAMPLE.bpmnWithPerm);
eq(bpmn.processName, '測試快速開發', '流程名稱');
eq(bpmn.activities.length, 6, '關卡數量');
eq(bpmn.formRefs.length, 1, 'FormType 引用數量');
eq(bpmn.formRefs[0].id, 'quickDevTestFormImport', '表單引用 ID');
eq(bpmn.formRefs[0].formDefinitionId, 'quickDevTestFormImport', 'formDefinitionId');
eq(bpmn.formRefs[0].name, '快速開發測試', '表單引用中文名');

const A = {};
bpmn.activities.forEach(a => A[a.id] = a);
eq(Object.keys(A).sort().join(','),
  'ACT_CreateForm_06,ACT_End_04,ACT_ManagerApprove_02,ACT_ManualTask_05,ACT_SendNotify_01,ACT_Start_03',
  '關卡 ID 清單');
eq(A.ACT_CreateForm_06.name, '開單', '開單關卡名稱');
eq(A.ACT_CreateForm_06.type, 'UserTask', '開單關卡型別');
ok(A.ACT_SendNotify_01.editable, 'SendTask 有 formFieldAccessDefinition → 可設定');
ok(!A.ACT_Start_03.editable && !A.ACT_End_04.editable, 'StartEvent / EndEvent 無節點 → 不可設定');
ok(A.ACT_ManagerApprove_02.human && A.ACT_ManualTask_05.human, 'UserTask / ManualTask 標記為人工關卡');

// ---------------------------------------------------------------- 2. 既有權限還原（驗收標準）
console.log('\n[2] 既有權限還原');
const ids = (act) => {
  const g = Core.getGroup(act, 'quickDevTestFormImport', false);
  return g ? Array.from(g.entries.keys()).join(',') : '';
};
eq(ids(A.ACT_CreateForm_06), 'TEST_Button_06,TEST_DialogInputLabel_12,TEST_DialogInputMulti_13', '[開單] 既有權限');
eq(ids(A.ACT_ManagerApprove_02), 'TEST_TextBox_07', '[主管] 既有權限');
eq(ids(A.ACT_ManualTask_05), 'TEST_DialogInputLabel_12,TEST_DialogInputMulti_13,TEST_DoubleTextBox_14,TEST_Dropdown_17', '[人工任務] 既有權限');
eq(ids(A.ACT_SendNotify_01), '', '[通知任務] 無既有權限');
eq(Core.getGroup(A.ACT_CreateForm_06, 'quickDevTestFormImport', false).entries.get('TEST_Button_06'), 'ENABLED', '權限值為 ENABLED');

// ---------------------------------------------------------------- 3. FORM 解析
console.log('\n[3] FORM 解析');
const fsrc = readXml(SAMPLE.formRenamed);
const form = Core.parseForm(fsrc.text, SAMPLE.formRenamed);
eq(form.formId, 'quickDevTestForm', 'formId');
eq(form.formName, '快速開發測試', '表單中文名');
eq(form.fields.length, 27, '元件總數');
const F = {};
form.fields.forEach(f => F[f.id] = f);
eq(F.TEST_Button_06.name, '按鈕', 'TEST_Button_06 中文名');
eq(F.TEST_Button_06.type, 'BUTTON', 'TEST_Button_06 型別');
eq(F.TEST_TextBox_07.name, '輸入框', 'TEST_TextBox_07 中文名');
eq(F.TEST_DialogInputLabel_12.name, '按鈕+雙輸入框', 'TEST_DialogInputLabel_12 中文名');
eq(F.TEST_Dropdown_17.name, '下拉選擇', 'TEST_Dropdown_17 中文名');
eq(F.TEST_Attachment_05.name, '檔案上傳', '附件中文名');
eq(F.TEST_CheckBox_16.typeLabel, '複選按鈕', '複選按鈕型別');
eq(F.TEST_Password_23.typeLabel, '密碼', '密碼型別');
eq(F.TEST_ListBox_18.typeLabel, '列表', '列表型別');
eq(F.TEST_Dropdown_17.typeLabel, '下拉選單', '下拉選單型別');
const grantable = form.fields.filter(f => f.grantable);
eq(grantable.length, 18, '可授權元件數（預設顯示）');
eq(form.fields.filter(f => !f.grantable).map(f => f.type).join(','),
  'HIDDEN,TITLE,HORIZONTAL_LINE,LABEL,SUBTAB,IMAGE,LINK,BARCODE,QRCODE', '預設收起的版面/裝飾類型');
ok(form.fields.every(f => bpmnHasNoDup(f.id)), '元件 ID 無重複');
function bpmnHasNoDup(id) { return form.fields.filter(f => f.id === id).length === 1; }

// 所有既有權限的 ID 都能在表單中找到（無孤兒）
const allPermIds = new Set();
bpmn.activities.forEach(a => a.groups.forEach(g => g.entries.forEach((v, k) => allPermIds.add(k))));
eq(Array.from(allPermIds).filter(id => !F[id]).join(',') || '(無)', '(無)', 'BPMN 權限 ID 全部對應得到表單元件');

// ---------------------------------------------------------------- 4. 無損回寫
console.log('\n[4] 無損回寫（位元組層級）');
const rank = (fid, id) => (fid === 'quickDevTestFormImport' && F[id]) ? F[id].index : 1e9;

// 4-1 全部標記 dirty 但不改內容 → 必須完全等於原檔
const t1 = Core.parseBpmn(src.text, 'x.bpmn');
t1.activities.forEach(a => a.dirty = true);
const r1 = Core.buildOutput(t1, rank);
eq(r1.text.length, src.text.length, '未改動時長度不變');
ok(r1.text === src.text, '未改動時輸出與原檔逐字元相同');
eq(r1.changes.length, 0, '未改動時 changes 為空');

// 4-2 主管關卡加一個欄位
const t2 = Core.parseBpmn(src.text, 'x.bpmn');
const t2a = t2.activities.find(a => a.id === 'ACT_ManagerApprove_02');
Core.getGroup(t2a, 'quickDevTestFormImport', true).entries.set('TEST_Button_06', 'ENABLED');
t2a.dirty = true;
const r2 = Core.buildOutput(t2, rank);
eq(r2.changes.length, 1, '只更動 1 個關卡');
eq(r2.changes[0].action, 'updated', '動作為 updated');
const back2 = Core.parseBpmn(r2.text, 'x.bpmn');
const b2a = back2.activities.find(a => a.id === 'ACT_ManagerApprove_02');
eq(Array.from(Core.getGroup(b2a, 'quickDevTestFormImport', false).entries.keys()).join(','),
  'TEST_Button_06,TEST_TextBox_07', '新增後依表單版面順序排列（Button_06 在 TextBox_07 前）');
eq(back2.activities.length, 6, '回寫後關卡數不變');
eq(r2.text.split('\n').length, src.text.split('\n').length, '行數不變');
// 其餘關卡逐字不動
eq(back2.activities.find(a => a.id === 'ACT_CreateForm_06').originalRaw,
  A.ACT_CreateForm_06.originalRaw, '其他關卡的權限字串未被更動');

// 4-3 清空主管關卡 → 整個標籤移除
const t3 = Core.parseBpmn(src.text, 'x.bpmn');
const t3a = t3.activities.find(a => a.id === 'ACT_ManagerApprove_02');
Core.getGroup(t3a, 'quickDevTestFormImport', false).entries.clear();
t3a.dirty = true;
const r3 = Core.buildOutput(t3, rank);
eq(r3.changes[0].action, 'removed', '清空 → removed');
ok(r3.text.indexOf('TEST_TextBox_07&gt;ENABLED') < 0, '權限字串已移除');
ok(!/formFieldAccessControl/.test(r3.text.slice(
  r3.text.indexOf('<formFieldAccessDefinition>', r3.text.indexOf('ACT_ManagerApprove_02') - 2000),
  r3.text.indexOf('ACT_ManagerApprove_02'))), '主管關卡已無 formFieldAccessControl 標籤');
eq(r3.text.split('\n').length, src.text.split('\n').length - 1, '移除後剛好少 1 行');
// 再把它加回來 → 應回到原始位元組
const t3b = Core.parseBpmn(r3.text, 'x.bpmn');
const t3c = t3b.activities.find(a => a.id === 'ACT_ManagerApprove_02');
Core.getGroup(t3c, 'quickDevTestFormImport', true).entries.set('TEST_TextBox_07', 'ENABLED');
t3c.dirty = true;
const r3d = Core.buildOutput(t3b, rank);
eq(r3d.changes[0].action, 'inserted', '補回 → inserted');
ok(r3d.text === src.text, '移除後再補回 → 與原檔逐字元相同（縮排/換行完全還原）');

// 4-4 對原本沒有 formFieldAccessControl 的 SendTask 插入
const t4 = Core.parseBpmn(src.text, 'x.bpmn');
const t4a = t4.activities.find(a => a.id === 'ACT_SendNotify_01');
Core.getGroup(t4a, 'quickDevTestFormImport', true).entries.set('TEST_TextBox_07', 'ENABLED');
Core.getGroup(t4a, 'quickDevTestFormImport', true).entries.set('TEST_Button_06', 'ENABLED');
t4a.dirty = true;
const r4 = Core.buildOutput(t4, rank);
eq(r4.changes[0].action, 'inserted', '無 control 標籤的關卡 → inserted');
const back4 = Core.parseBpmn(r4.text, 'x.bpmn');
const b4a = back4.activities.find(a => a.id === 'ACT_SendNotify_01');
eq(b4a.originalRaw,
  '&lt;FormFieldAccessControl&gt;&lt;quickDevTestFormImport&gt;&lt;TEST_Button_06&gt;ENABLED&lt;/TEST_Button_06&gt;&lt;TEST_TextBox_07&gt;ENABLED&lt;/TEST_TextBox_07&gt;&lt;/quickDevTestFormImport&gt;&lt;/FormFieldAccessControl&gt;',
  '插入的逃脫字串格式正確且已排序');
// 縮排與既有關卡一致
const line = r4.text.split('\n').find(l => l.indexOf('TEST_Button_06&gt;ENABLED') >= 0);
const refLine = src.text.split('\n').find(l => l.indexOf('TEST_TextBox_07&gt;ENABLED') >= 0);
eq(line.match(/^\s*/)[0].length, refLine.match(/^\s*/)[0].length, '插入行縮排與既有寫法一致');
// 只有那一行是新增的，其餘全同
const d4 = r4.text.split('\n'), d0 = src.text.split('\n');
eq(d4.length, d0.length + 1, '剛好多 1 行');
eq(d4.filter(l => d0.indexOf(l) < 0).length, 1, '只有 1 行是新內容');

// 4-5 多關卡同時變更
const t5 = Core.parseBpmn(src.text, 'x.bpmn');
t5.activities.filter(a => a.editable).forEach(a => {
  const g = Core.getGroup(a, 'quickDevTestFormImport', true);
  g.entries.clear();
  form.fields.filter(f => f.grantable).forEach(f => g.entries.set(f.id, 'ENABLED'));
  a.dirty = true;
});
const r5 = Core.buildOutput(t5, rank);
eq(r5.changes.length, 4, '4 個可設定關卡全部更新');
const back5 = Core.parseBpmn(r5.text, 'x.bpmn');
eq(back5.activities.filter(a => a.editable).every(a =>
  Array.from(Core.getGroup(a, 'quickDevTestFormImport', false).entries.keys()).length === 18), true,
  '每個關卡都寫入 18 個可授權元件');
eq(back5.activities.length, 6, '關卡數仍為 6');
eq(r5.text.split('\n').length, src.text.split('\n').length + 1, '僅通知任務多 1 行');

// 4-6 未載入 .form（rank 全部相同）時，順序維持原樣、輸出不變
const t6 = Core.parseBpmn(src.text, 'x.bpmn');
t6.activities.forEach(a => a.dirty = true);
const r6 = Core.buildOutput(t6, () => 1e9);
ok(r6.text === src.text, '未載入 .form 時仍能位元組還原');

// ---------------------------------------------------------------- 5. 其他 BPMN 檔相容性
console.log('\n[5] 其他樣本檔相容性');
for (const f of [SAMPLE.bpmnOriginal, SAMPLE.bpmnWithPerm]) {
  const s = readXml(f);
  const p = Core.parseBpmn(s.text, f);
  const t = Core.parseBpmn(s.text, f);
  t.activities.forEach(a => a.dirty = true);
  const r = Core.buildOutput(t, rank);
  ok(p.activities.length > 0 && r.text === s.text, `${f}：${p.activities.length} 關卡，回寫位元組不變`);
}
const qf = readXml(SAMPLE.formOriginal);
const qform = Core.parseForm(qf.text, SAMPLE.formOriginal);
eq(qform.fields.length, 27, `${SAMPLE.formOriginal} 元件數`);

console.log(`\n${'='.repeat(50)}\n通過 ${pass} 項，失敗 ${fail} 項\n${'='.repeat(50)}`);
process.exit(fail ? 1 : 0);
