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
python probe_api.py       # ② 對 191 實測唯讀方法，存下真實回傳樣本
python build_manual.py    # ③ 合成 API 手冊
```

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
- 📖 **呼叫前必讀**：視覺化呈現 rpc/encoded、回傳 string 四種型態、假成功防範與欄位 ID 地雷。
- ⚙️ **種子資料庫**：檢視與複製測試用參數種子出處。


| 檔案 | 角色 | 誰維護 |
|:---|:---|:---|
| `wsdl_dump.py` | 抓 WSDL → 方法與參數清單 | 機器 |
| `ws_client.py` | 手刻 rpc/encoded 的 SOAP 客戶端 | 機器 |
| `probe_api.py` | 實測與分級 | 機器 |
| `seeds.json` | 實測用的參數值（帳號、單號、OID…） | 人 |
| `notes.json` | 各方法的用途與語意註記 | **人** |
| `build_manual.py` | 三者合成手冊 | 機器 |
| `docs/WorkflowService_API手冊.md` | 主產出 | 自動產生，**勿手改** |

`out/payloads/`、`out/probe_result.*` 含真實單據與員工姓名，已列入 `.gitignore`。

## 目前進度

| 狀態 | 數量 |
|:---|---:|
| 方法總數 | 65 |
| 實測成功、有回傳樣本 | 29 |
| 已寫下用途與參數語意 | 39（含 4 支由既有 Node 服務驗證） |
| 未實測（有副作用，需可拋棄的測試單） | 33 |
| 實測失敗（環境或參數未知） | 3 |

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

其餘要點（回傳型別、假成功、欄位 id 地雷）都寫在
[docs/WorkflowService_API手冊.md](docs/WorkflowService_API手冊.md) 的「呼叫前必讀」。

## 換一台主機或換測試流程

`seeds.json` 裡的單號、OID、工作項目 OID 都綁在特定的測試單上，換環境要重抓。
`_來源` 欄位記錄了每個值是從哪支 API 撈到的，照著跑一遍即可。
同名參數在不同方法需要不同狀態的單子（例如作廢意見只有已終止的單才有），
用 `_overrides` 依方法覆寫。
