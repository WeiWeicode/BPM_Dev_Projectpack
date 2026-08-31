# 5_ws_explorer —— BPM SOAP API 擷取與實測

把鼎新 BPM 的 SOAP 服務（NaNaWeb `WorkflowService`）從「只有方法名稱」
推進到「知道怎麼用」：抓 WSDL、對測試區實測、把結果寫成 API 手冊。

只用 Python 標準函式庫，無需安裝任何套件。

## 邊界

| 對象 | 允許範圍 |
|:---|:---|
| 191 測試區 `10.10.130.191:8080` | 可自由呼叫，含有副作用的方法 |
| **190 正式區** | **一律不連**，`probe_api.py` 傳入 190 會直接拒絕執行 |
| 測試區資料 | 不刪除既有資料；API 產生的新單留著即可 |

`probe_api.py` 預設**只呼叫唯讀方法**。開單、簽核、作廢這類有副作用的方法
必須 `--method` 指名並加 `--allow-write`，不接受整批送出。

## 四個步驟

```bash
cd 5_ws_explorer
python wsdl_dump.py       # ① 抓 WSDL，擷取 65 支方法的參數與回傳型別
python probe_api.py       # ② 實測唯讀方法，存下真實回傳樣本
python probe_write.py     # ③ 實測有副作用的方法（會開單、簽核，跑完自動收單）
python build_manual.py    # ④ 合成 API 手冊
```

`probe_write.py` 會在測試區開出真實的簽核單。它每個情境自己開新單、
不動既有單據，結束時把開出來的單全部作廢或終止，不留待辦給別人。

④ 是人工的：把新學到的語意寫進 `notes.json`，再跑一次 `build_manual.py`。

## ⑤ 視覺化手冊與線上即時實測工作台 (Vue + FastAPI)

除了文字版手冊外，本專案提供視覺化的 Vue 網頁應用與即時實測工作台：

```bash
# 1. 啟動後端（port 8001）
cd 5_ws_explorer/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001

# 2. 啟動前端開發伺服器（port 5174）
cd 5_ws_explorer/frontend
npm install
npm run dev
```

開啟瀏覽器前往 <http://localhost:5174> 即可：
- 📑 **API 手冊與目錄**：65 支方法多維度篩選（唯讀/副作用/實測狀態/信心）、參數規格與回傳樣本。
- ⚡ **即時實測工作台**：線上填入參數、一鍵代入種子、發送 SOAP 請求至 191 測試區並即時檢視回傳 XML 與 SOAP 封包。
- 📝 **流程工作台**：三種模式共用左邊的流程／單號搜尋。
  **改既有單** 挑單（進行中／已結案）→ 帶出欄位 id、中文名稱、型別與現值 → 逐欄編輯 → 送出後讀回驗證（`updateFormValueBySerialNember`）。
  **建立新單** 取空白表單範本 → 填欄位 → 指定申請人與部門 → 開單後讀回驗證（`invokeProcess` / `invokeProcessByOrg`）。
  **關卡操作** 看簽核歷程 → 以該關卡的待辦人身分 → 簽收、改表單後簽核推進、轉派、取回重辦、收單。
- 📖 **呼叫前必讀**：視覺化呈現 rpc/encoded、回傳 string 四種型態、假成功防範與欄位 ID 地雷。
- ⚙️ **種子資料庫**：檢視與複製測試用參數種子出處。

### 流程工作台為什麼要獨立一頁

`updateFormValueBySerialNember` 是**整份覆寫**，不是合併。實測：

| 送出 | 讀回 |
|:---|:---|
| 完整 15 欄、只改其中 2 欄 | 15 欄，只有那 2 欄變 |
| 只送要改的 1 欄 | **剩 1 欄**，其餘 14 欄整個消失 |

它也不驗證欄位 id 與 XML 結構。把 `fetchFormInstanceWithProcSerlNo` 的整包回傳
（`FormCollection`）當成 `pFormValue` 貼回去，BPM 照收，表單第一層變成
`FormCollection` 而非表單 id，畫面上所有欄位就退回預設值 —— 看起來像資料被清空，
其實只是多包了一層。這一頁因此**不讓人手貼 XML**：前端只送「哪個欄位改成什麼」，
後端在寫入前重讀現值、只替換目標欄位內文、整份送回，再讀回逐欄比對。
偵測到被包壞的單會直接標紅並提供一鍵修復。

建立新單也是同一個道理：`invokeProcess` **不驗證欄位 id**，自己拼的欄位會被靜默寫入，
要到之後 `fetchUniFormatFormInstance*` 讀取時才爆，所以欄位結構一律取自
`getFormFieldTemplate`。另外三件實測到的事會直接顯示在畫面上：

- **開單失敗一樣會消耗單號**，失敗不代表沒留下痕跡。
- 流程若設了主旨範本，`pSubject` 送的值會被蓋掉 —— 送出後會列出實際主旨供比對。
- 讀回時「送空值卻被回填」與「送了值卻寫不進去」是兩回事。前者是流程自己該做的
  （例如 `SerialNumber` 自動配號：送 `''` 回 `SPCP202608_0028`），後者才是問題。
  兩類分開顯示，不混為一談，也不靜默吃掉。

### 關卡操作與「模擬該關卡的使用者」

這組 API 沒有登入概念，操作者一律由參數指定，而且指定錯了會被擋
（`acceptWorkItem` 的 pUserId 必須是待辦目前擁有者、`assigneeReassignWorkItem`
的 pRequesterOID 也是）。所以關卡模式先從簽核歷程解析出目前關卡的待辦人
（`performerName` 格式是「員工編號_姓名」），列出來讓人挑身分，
再以那個人送出 —— 不必自己查是誰，也不必記 Users.OID。

實測（`quickDevTestProcessImportWebTool`，2026-08-31）確認的順序與語意：

| 項目 | 實測結果 |
|:---|:---|
| `checkWorkItemState` | **0 = 未簽收，1 = 已簽收** |
| 未簽收就 `completeWorkItem` | 回 `The workitem is not running state` |
| 已簽收又送 `acceptWorkItem` | 回 `The workitem has been performed` —— 正常情況，先查狀態再決定簽不簽 |
| `reexecuteActivity` | 目前關卡變 `closed.terminated`，被取回的關卡重新 `open.running` |
| `terminatedProcessForSerialNo` | **會檢查操作者權限**，回 `The user(id=…) cannot terminat this process` 時改用作廢 |

`completeWorkItem` 先前在 `SP_DetectionOPProcess` 一律失敗，根因是該流程引用的群組
`SPDetectionOPGroup` 不在測試區 `Groups` 表裡 —— 與 API 無關，換一支流程就正常。

轉派需要 **Users.OID（不是 Employee.OID）**，只能查唯讀資料庫。查不到時
轉派按鈕會停用並說明原因，其餘操作不受影響。

**新增關卡目前做不到**，原因寫在 `notes.json` 的 `addCustomActivity`：
清單元素類別已確認是 `com.dsc.nana.data_transfer.ActivityDefinitionForClientListDTO`，
但元素內容格式沒解出來（`performerId` 既不是子元素也不是 XML 屬性），
`addCloneSerialActivity` 則不論參數組合一律交易失敗。所以這一頁不提供假的加關卡按鈕。

欄位的中文名稱與型別來自 `3_db_explorer` 的 `bpm_kb`（唯讀連線）。
沒有 `.env` 或未裝 pyodbc 時這一頁照常可用，只是名稱欄留白並註明原因，不靜默假裝。
流程清單讀 `3_db_explorer/out/form_process_map.json`（WorkflowService 沒有
「列出所有流程」的方法，`fetchProcInstances` 一定要先給 `pProcessId`）。


| 檔案 | 角色 | 誰維護 |
|:---|:---|:---|
| `wsdl_dump.py` | 抓 WSDL → 方法與參數清單 | 機器 |
| `ws_client.py` | 手刻 rpc/encoded 的 SOAP 客戶端 | 機器 |
| `probe_api.py` | 唯讀方法的實測與分級 | 機器 |
| `probe_write.py` | 有副作用方法的情境式實測 | 機器 |
| `seeds.json` | 實測用的參數值（帳號、單號、OID…） | 人 |
| `notes.json` | 各方法的用途與語意註記 | **人** |
| `build_manual.py` | 三者合成手冊 | 機器 |
| `docs/WorkflowService_API手冊.md` | 主產出 | 自動產生，**勿手改** |

`out/payloads/`、`out/probe_result.*` 含真實單據與員工姓名，已列入 `.gitignore`。

## 目前進度

65 支方法（60 個方法名，其中 5 個有多載）**全部都有用途與參數語意的記錄**。

| 實測結果 | 操作數 | 說明 |
|:---|---:|:---|
| 唯讀方法執行成功 | 33 | 全數成功，回傳樣本存於 `out/payloads/` |
| 有副作用方法執行成功 | 25 | 實際開單、簽收、轉派、跳關、取回重辦、作廢 |
| 執行失敗 | 6 | 原因都已查明，見下表 |
| 刻意未執行 | 1 | `importOrganizationData` |

失敗的 6 支不是「測不出來」，是查到了真正的原因：

| 方法 | 原因 |
|:---|:---|
| `invokeProcess`（四參數）<br>`invokeProcessByOrg`（五參數） | 不帶表單值就開不了單，此流程的表單有必要欄位 |
| `invokeProcessByParameter`<br>`invokeProcessByParameterByOrg` | 測試流程第一關是申請人、未設定成可用參數啟動 |
| `addCloneSerialActivity` | 來源關卡與參考關卡指向同一個時交易無法提交 |
| `completeWorkItem` | **測試區資料缺漏**：流程引用群組 `SPDetectionOPGroup`，但 `Groups` 表 581 筆裡沒有這個群組。與 API 無關，換一支流程才驗得出來 |

`importOrganizationData` 是唯一刻意不測的：它會覆寫組織資料，
匯入內容不完整等同刪除既有部門，與「不刪測試區資料」的約定牴觸。

## 這支服務的特徵

| 項目 | 值 |
|:---|:---|
| Endpoint | `http://10.10.130.191:8080/NaNaWeb/services/WorkflowService` |
| targetNamespace | `http://webservice.nana.dsc.com/` |
| 產生器 | Apache Axis 1.3 |
| SOAP 風格 | `rpc` / `encoded`（**不是** document/literal） |
| 參數型別 | 只有 `string`、`int`、`boolean`，沒有 `<wsdl:types>` |

**Python 的 zeep 接不上這個服務**（不支援 SOAP encoding），所以 `ws_client.py`
手刻 envelope。Node 端的 `soap` 套件則可正常運作 ——
`BPMbackend/BPMxml/bpmbackXmlController.js` 就是這樣用的。

其餘要點都寫在
[docs/WorkflowService_API手冊.md](docs/WorkflowService_API手冊.md) 的「呼叫前必讀」，
其中四個是實測才問得出來、WSDL 上完全看不到的：

1. 回傳的 `string` 有四種形態（XStream 物件／屬性式 XML／逗號清單／純量）。
2. 有兩支方法把例外包在回傳字串裡，HTTP 200 但內容是 `<NotFoundException>`。
3. `invokeProcess` 不驗證表單欄位 id，錯的欄位靜默寫入、延後爆炸。
4. 使用者 OID 要用 `Users.OID` 而非 `Employee.OID`，兩者只差一個字元。

## 換一台主機或換測試流程

`seeds.json` 裡的單號、OID、工作項目 OID 都綁在特定的測試單上，換環境要重抓。
`_來源` 欄位記錄了每個值是從哪支 API 撈到的，照著跑一遍即可。
同名參數在不同方法需要不同狀態的單子（例如作廢意見只有已終止的單才有），
用 `_overrides` 依方法覆寫。
