# bpm_kb —— 讓 AI 讀懂鼎新 BPM 的表單與簽核流程

從 BPM 資料庫直接把表單定義、流程邏輯撈出來，轉成結構化 JSON 與一份重點文件，
讓 AI（或新進人員）不必翻設計師介面就能理解一支流程在做什麼。

一律**唯讀**連線，`Database` 以 `readonly=True` 開啟，CLI 的 `sql` 指令只接受
`SELECT` / `WITH`。

## 安裝與設定

```bash
pip install -r requirements.txt
```

複製 `.env.example` 為 `.env` 並填入帳密（`.env` 已列入 `.gitignore`）：

```
BPM_DB_HOST=10.10.130.191
BPM_DB_NAME=NaNa
BPM_DB_USER=...
BPM_DB_PASSWORD=...
```

## 用法

```bash
python bpm_kb_tool.py check      # 測試連線
python bpm_kb_tool.py probe      # 探索資料表，寫出 schema 快照
python bpm_kb_tool.py forms      # 列出表單與版本
python bpm_kb_tool.py processes  # 列出流程與版本
python bpm_kb_tool.py pull       # 撈 XML、組流程圖、產生重點文件
python bpm_kb_tool.py digest     # 只重產文件（用 out/ 既有結果）
```

共用選項：`--days=N`（預設 7 天內）、`--all`（不限日期）、`--latest`（每個 id 只留最新版）。
第一個位置參數是關鍵字，會比對 id 與名稱：

```bash
python bpm_kb_tool.py pull quickDevTest --days=30
```

產出：

- `out/forms/<id>_v<n>.form` + `.json` —— 表單 XML 與欄位清單
- `out/processes/<id>_v<n>.bpmn` + `.json` —— 畫布 XML 與完整流程結構
- `docs/schema/schema_snapshot.json` —— 資料表／欄位／定義欄位快照
- `docs/BPM_知識重點.md` —— 給人與 AI 讀的重點整理

## 資料模型（由 probe 實測得出）

表單與流程的存法完全不同，這是理解整個系統的關鍵：

```
表單：整份 XML 存一格
  FormDefinition.defSerialize          .form 本體
  FormDefinition.script / rwdLayout    JS 與版面，另外存
  FormDefinition.containerOID          表單的邏輯身分，各版本共用
  FormDefinition.version / publicationStatus / validFrom / validTo

流程：拆進關聯表
  ProcessPackage                       流程套件，一個版本一筆
   ├─ headerOID            → ProcessPackageHeader    createdTime
   ├─ redefinableHeaderOID → RedefinableHeader       version / publicationStatus
   └─ OID → ProcessPackage_ProcessDef → ProcessDefinition
                                          bpmXML = 畫布座標，不含邏輯
                                          OID 即以下各表的 containerOID
        ActivityDefinition               關卡
         └─ formFieldAccessDefinitionOID → FormFieldAccessDefinition
                                            formFieldAccessControl = 欄位權限
        TransitionDefinition             連線 from → to
        ParticipantDefinition            執行者
```

匯出的 `.bpmn` 檔是設計師把這些關聯表重新序列化的結果，資料庫裡沒有一個欄位
長得跟它一樣 —— `process_graph.py` 做的就是反向把它組回來。

## 模組

| 模組 | 職責 |
| --- | --- |
| `config.py` | 讀 `.env`、挑 ODBC 驅動、組連線字串 |
| `db.py` | 唯讀查詢封裝；`big_text()` 處理 `ntext` 轉型 |
| `probe.py` | 掃資料表與大文字欄位，抽樣找出 `com.dsc.*` 序列化欄位 |
| `extract.py` | 表單／流程清單與 XML 落地 |
| `process_graph.py` | 從關聯表組回關卡、連線、執行者、欄位權限 |
| `digest.py` | 產生 `docs/BPM_知識重點.md` |
| `cli.py` | 命令列進入點 |

表單與流程 XML 的解析共用既有的 `core.form_handler` / `core.bpmn_handler`，
避免兩份實作各自漂移。

## 已知限制

- `probe` 只抓開頭為 `<com.dsc.` 的欄位，所以 `ProcessDefinition.bpmXML`
  （開頭是 `<?xml`）不會出現在探索結果中，它是靠 `extract.py` 明確指定的。
- 舊版流程（鼎新改版前匯入的）欄位結構未必相同，預設只看近 7 天，
  要處理舊單請用 `--days=N` 或 `--all` 並自行確認結果。
- `ActivityDefinition.activityTypeOID` 尚未解析，關卡的 BPMN 型別目前
  改由 `bpmXML` 的 `Node ClassName` 補齊。
- 條件式（`TransitionDefinition.conditionOID`）目前只記錄「有無條件」，
  尚未展開條件內容。
