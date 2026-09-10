# 8_BPMAIworker 計畫書

---

## 1. 成功標準

分三級，一級沒過就不談下一級：

| 級別 | 標準 | 怎麼驗 |
|:---|:---|:---|
| **L1 結構可還原** | 產出的 `.form` / `.bpmn` 用 `1_xml_tool/core` 反解後，欄位／關卡／權限與當初的 IR **逐項相等** | `builder` 自檢，程式判定 |
| **L2 設計師可開啟** | 匯入鼎新設計師能開、能存、版面不跑位、無 `Cannot read properties of null` | 人工匯入 191 測試區 |
| **L3 可跑完一張單** | 發佈後實際開單、走完所有關卡，各關卡欄位權限與腳本行為符合 IR | `5_ws_explorer` 對 191 測試區實測 |

**L1 是程式該保證的；L2、L3 目前沒有任何自動化手段，只能人工。**
文件中凡是尚未通過 L2 的推論，一律標 ⚠️。

---

## 2. 管線

```
① 需求      人類講一段話 / 給一張紙本表格 / 指定一支參考流程
     ↓
② IR 產生   AI 讀《AI產生規格_IR.md》，輸出 form_ir.json + process_ir.json
     ↓
③ IR 校驗   程式檢查：ID 合法性、重複、關卡引用的欄位是否存在、起訖節點是否連通
     ↓
④ 組裝      builder 套 templates/ 的樣板 → 配 XStream 連號 id → 配 OID → 逃脫 → 寫檔
     ↓
⑤ 自檢      用 1_xml_tool/core 反解產出物，與 IR 對比（L1）
     ↓
⑥ 實測      人工匯入 191 測試區設計師（L2）→ 走一張單（L3）
```

**只有 ② 是 AI 做的。**③～⑤ 全是確定性程式，同樣的 IR 一定產出位元組相同的檔案。

---

## 3. 模組切分

| 模組 | 職責 | 不做什麼 |
|:---|:---|:---|
| `ir/schema.py` | IR 的結構定義與校驗訊息 | 不碰 XML |
| `builder/id_pool.py` | XStream 連號 `id` 配發與 `reference` 重寫 | 不知道業務語意 |
| `builder/oid.py` | 32 碼 OID 配發（前 8 碼遞增、後 24 碼固定） | — |
| `builder/form_builder.py` | IR → `.form` | 不產生 JS |
| `builder/bpmn_builder.py` | IR → `.bpmn`（含 `bpmXML` 座標自動排版與權限逃脫） | — |
| `builder/script_builder.py` | IR → `.js`（生命週期骨架 + 事件函式殼） | 不寫業務邏輯內容 |
| `templates/` | 從 `samples/` 抽出的樣板片段 | — |

**沿用不重寫**：解析一律用 `1_xml_tool/core`（`xml_utils` / `form_handler` / `bpmn_handler`），
不另寫 parser——AGENTS.md 第 7.5 節的理由同樣適用：兩份實作一定會漂移。

---

## 4. 樣板從哪裡來

不手寫樣板，一律從 `samples/` 的實際檔案裡切出來：

| 樣板 | 來源 | 用途 |
|:---|:---|:---|
| **空白專案骨架** | `templates/原始空白專案/`（設計器直接匯出） | **新專案的預設基底**，見 [templates/README.md](templates/README.md) |
| 27 種元件片段 | `samples/快速開發測試/表單/原檔案-quickDevTestForm.form` | 每種元件型別各切一份，這支檔正好一種一個 |
| 表單骨架 | 同上（去掉 `elementDefinitions` 內容） | 檔頭與尾端固定區 |
| 7 種關卡片段 | `samples/快速開發測試/流程/原檔案-測試快速開發.bpmn` | UserTask／SendTask／ManualTask／DecisionRuleTask／Start／End／Gateway |
| 流程骨架 | 同上 | `ProcessPackage` 外殼 |
| 實務寫法對照 | `samples/太陽能ECRECN/` | 25 關卡 × 100+ 欄位的上線流程，用來檢查樣板夠不夠用 |

> `samples/` 已列入 `.gitignore`（公司實際資料）。`templates/` 若含實際欄位名稱與中文標籤，
> **同樣不進版控**；只有結構骨架（欄位名清空）才能提交。

---

## 5. 里程碑

| 期別 | 產出 | 完成判準 |
|:---|:---|:---|
| **M0** ✅ | 五份手冊 + 本計畫 | 人能照文件手工重現一次產生流程 |
| **M0.5**（目前） | `templates/` 空白基底 + `tools/` 六支工具 | 一行指令複製出新專案，靜態檢查全過；`samples/AI設計的流程測試/` 為第一個實測件 |
| **M1** | `templates/` 切出、`ir/` schema 落地 | 用兩支 sample 反推出 IR，再由 IR 組回去，位元組不變 |
| **M2** | `form_builder` | 從 IR 產生新表單，通過 L1；人工匯入通過 L2 |
| **M3** | `bpmn_builder` | 從 IR 產生新流程（含權限），通過 L1、L2 |
| **M4** | `script_builder` + AI 提示詞 | 一句需求走完全程，通過 L3 |

**M1 的判準是刻意設計的**：把既有 sample 反推成 IR、再組回原檔，
如果位元組不變，代表樣板與編號規則吃透了；這個往返測試過不了，M2 以後全是空談。

---

## 6. 目前確認過的事實（有實測依據）

| 事實 | 依據 |
|:---|:---|
| `.form` 的 XStream `id` 為 1…N 嚴格連號，`reference` 用數字指回 | `原檔案-quickDevTestForm.form` 共 747 個 id、46 個 `reference="8"`（指向 `<cssDevice>`） |
| `.bpmn` 的 XStream `reference` 用**相對路徑**而非數字（`reference="../../.."`） | `原檔案-測試快速開發.bpmn` |
| `.bpmn` 的 OID 共用 24 碼後綴、前 8 碼遞增 | 76 個 OID，74 個後綴為 `f9e21004851cac97a977dbbf` |
| `rwdLayout` 是**逃脫過的 JSON**，12 欄格線 | `[{"rowType":"Title","id":"Title1"},{"row":[3,3,3,3],"column":[[12],…],"elements":[[{"id":"Label3"}],…]}]` |
| 表單與流程的綁定寫在 `relevantDataDefinitions` 的 `FormType.formDefinitionId` | `已完成匯入_測試快速開發-欄位權限.bpmn` |
| 權限值只有 `ENABLED` / `INVISIBLE` / `FULL_CONTROL`，唯讀＝不列出 | AGENTS.md 7.3、README.md 資料模型速查 |

## 7. 尚未驗證、會影響設計的未知數 ⚠️

誠實列出，這些是 M2 之前必須先問到答案的：

1. **OID 可不可以由我們自行編？** 匯入時鼎新是重新配發、還是沿用檔案內的值？
   若是沿用，自編的 OID 與線上既有資料撞號會發生什麼事，未知。
2. **`containerOID` 要不要留空／留舊值？** 新檔案沒有對應的線上定義，
   現有 sample 的值都是從既有定義帶出來的。
3. **`rwdLayout` 與 `elementStyles` 的座標必須一致到什麼程度**？
   目前兩處都有版面資訊（格線 JSON 與 `coordinateX/Y`），何者為準未實測。
4. **設計師匯入時是否驗證 XStream id 連號**，還是只要 XML 合法就收。
5. **`multiZhMap`（多語系對照）留空是否會出事**。

在 1、2 兩點問到答案之前，M2 的作法是**保守路線**：
一律從一份既有的、確定能匯入的檔案「改造」而非「憑空生成」——
沿用其骨架與 OID 配發方式，只增刪元件。

---

## 8. 邊界

- 產出物一律寫到工作目錄，**絕不覆蓋 `samples/` 內的原檔**（沿用 ①② 的 `已完成_` 命名精神）。
- 本工具**不連資料庫、不呼叫 SOAP**。要驗證產出物，用 ⑤ 對 **191 測試區**；190 正式區一律不碰。
- 不引入第三方套件。XML 一律走 `1_xml_tool/core` 的字串區間法，**禁用 lxml／BeautifulSoup**
  （AGENTS.md 7.2：任何重新序列化都會破壞 XStream 參照與空白格式）。
