# 鼎新 BPM (BPM5892) 系統初步分析

> 分析日期：2026-09-07
> 分析範圍：`D:\檔案分享\BPM\BPM5892\wildfly-15.0.0.Final`
> 性質：快速盤點（非逐檔掃描）

---

## 一、結論摘要

1. 這是**鼎新 BPM**（產品內部代號 **EFGP**，流程引擎代號 **NaNa**）跑在 **WildFly 15.0.0.Final** 上的一套系統。
2. 本目錄為**測試區的複製品**，非線上執行中的實例（log 最後一筆為 2026-09-07）。
3. **完全沒有任何加密或混淆。** 前端（JSP / JavaScript）是完整可讀的原始碼且帶中文註解；後端 Java 則是編譯後的 `.class`，但套件與類別名稱皆未混淆。
4. **原本 65GB 中有 65.48GB 是 log 檔**，實際有意義的內容不到 0.4GB。
   → 已於 2026-09-07 清理，釋出 65.0 GB（詳見第六節）。
5. 2026-09-07 補上 `standalone\` 目錄後，才取得應用程式本體（12 個部署單元 / 1.1 GB）與真正的伺服器設定（詳見第九節）。

---

## 二、技術棧

| 層次 | 使用技術 |
|---|---|
| 應用伺服器 | WildFly 15.0.0.Final (JBoss) |
| 伺服器端語言 | **Java（Java EE / EJB 3）** |
| 主要 package | `com.dsc.nana.*`、`com.digiwin.bpm.*` |
| 持久層 | JPA + Hibernate |
| 主資料庫 | MS SQL Server（Dialect: `com.digiwin.bpm.*.util.hibernate.SQLServer2000Dialect`） |
| 支援的 DB Driver | MSSQL / Oracle / DB2 / MySQL / PostgreSQL / Sybase / Informix / AS400 / FoxPro / 達夢 DM8 |
| Web MVC 框架 | **Apache Struts 1.3**（`struts-config`、struts-bean/html/logic 標籤庫） |
| 前端（傳統） | JSP + JavaScript + jQuery UI + Bootstrap |
| 前端（新版） | NaNaXWeb.war，4,805 個 js + 72 個 TypeScript |
| 樣板引擎 | FreeMarker（`.ftl`） |
| AOP | AspectJ（aspectjweaver-1.8.9） |
| Ajax 框架 | **DWR**（Direct Web Remoting），介面在 `dwrDefault/interface/ajax_*.js` |
| 排程 | **Quartz**（設定於 `NaNaJobs.xml`） |
| Web Service | Apache Axis (`/webservice/servlet/AxisServlet`) + RESTful |
| 流程定義格式 | **XPDL**（WfMC 標準），以 **Castor** 做 XML ↔ Java 物件對映 |
| 報表 / PDF | easypdf.jar、easypdf-jacob.jar、jacob.jar（透過 COM 呼叫 MS Office） |
| 字型 | Arial-Unicode-MS.ttf（PDF 轉檔用，23MB） |

---

## 三、目錄結構與容量

```
wildfly-15.0.0.Final\
├── appclient\          2 檔        0.00 GB
├── bin\            1,757 檔        0.12 GB   啟動腳本 + 執行期資料夾
├── docs\             437 檔        0.01 GB   WildFly 原廠 schema/範例
├── domain\            10 檔        0.00 GB   WildFly 預設設定（未使用）
├── modules\        6,618 檔       65.85 GB   ← 其中 NaNa\log 佔 65.48 GB（已清理，現 478 MB）
├── standalone\                     1.80 GB   ← 2026-09-07 補上（應用程式本體，見第九節）
│   ├── deployments\                1.10 GB      12 個部署單元
│   ├── data\                       0.71 GB      content 663M + activemq 44M
│   └── configuration\              169 KB       standalone-full.xml（真正的伺服器設定）
└── welcome-content\    9 檔        0.00 GB
```

### 副檔名分布（排除 log 後）

| 數量 | 副檔名 | 說明 |
|---|---|---|
| 1,616 | (無) | 多為 module 目錄結構檔 |
| 540 | .jar | **全部是 WildFly 原廠系統模組，無任何 BPM 應用 jar** |
| 506 | .xml | 設定檔 / Castor mapping |
| 371 | .xsd | WildFly subsystem schema |
| 51 | .pkc | JBoss Modules 的 class-path 快取（與 BPM 無關） |
| 27 | .properties | NaNa 系統設定 |
| 5 | .form | 表單定義 |

---

## 四、程式碼可見範圍

> 初版分析時 `standalone\` 尚未複製過來，故結論為「看不到程式碼」。
> 2026-09-07 補齊後重新確認如下。

### 4.1 結論：沒有加密，也沒有混淆

| 類型 | 數量 | 可讀性 |
|---|---|---|
| **JSP**（NaNaWeb.war） | 565 | ✅ **完整原始碼**，Struts 標籤庫，可直接閱讀修改 |
| **JavaScript**（NaNaWeb.war） | 1,423 | ✅ **完整原始碼**，未壓縮未混淆，**帶中文註解** |
| **JavaScript**（NaNaXWeb.war） | 4,805 | ✅ 新版前端，另含 72 個 `.ts` |
| **FreeMarker 樣板** `.ftl` | 111+ | ✅ 可讀 |
| **CSS / SVG / HTML** | 1,200+ | ✅ 可讀 |
| **Java** `.class` | 1,228（NaNaWeb）+ 各模組 | ⚠️ 編譯後位元碼，**但套件/類別名稱未混淆** |
| **Java** `.java` | 0（鼎新自有程式） | ❌ 不隨產品交付 |

驗證方式與結果：

- `js/common_util.js`：441 行、平均行長 26 字元、開頭即為中文註解 → 確定未經 minify 或 obfuscate
- 掃描 `NaNaWeb.war/WEB-INF/lib` 全部 jar：唯一含 `.java` 的是 **Apache Struts 開源套件**（struts-core / taglib / tiles / extras，共 323 個），鼎新自有 jar 皆為純 `.class`
- `nana-services-client.jar`：2,553 個 `.class`，套件路徑清晰可辨（`com/dsc/nana/util/search/`、`com/dsc/nana/util/mobile/wechat/` 等）

### 4.2 實務意義

- **前端邏輯完全開放** —— 表單驗證、畫面行為、AJAX 呼叫流程都能直接讀，客製化改動也是改這一層。
- **後端商業邏輯是 binary** —— 技術上 `.class` 未混淆、反編譯可還原度很高，但屬原廠商業授權範圍，通常不被允許。
- 鼎新交付給客戶的一向只有 binary，Java 原始碼不隨產品交付。

---

## 五、這份拷貝中「看得到」的邏輯

### 5.1 `modules\NaNa\conf\` — 系統設定（資訊量最大）

| 檔案 | 內容 |
|---|---|
| `NaNaWeb.properties` | SSO 機制（CAS / SAML / SAP NetWeaver / Post 驗證）、免驗證 URL 白名單、GZIP 設定、多主機在地化設定 |
| `NaNaJobs.xml` | Quartz 排程清單（`BatchNoticeDeprecatedJob`、`AutoPerformInvokeActJob` 等），Job class 統一為 `com.dsc.nana.user_interface.web.schedule.SystematicJob` |
| `NaNaPlugIn.xml` | 外掛機制：可在指定 EJB 方法的 begin / end 掛 handler（目前 `enabled=false`） |
| `NaNaIntSys.properties` | 與**鼎新 TIPTOP ERP** 的整合設定、AppForm 多語系對映、費用申請流程欄位對映 |
| `liusconfig.xml` | 流程服務設定（15KB） |
| `castor\` | XPDL 匯入 / 匯出的 XML mapping（各約 45KB） |
| `syncorg\` | 組織架構 ETL 同步定義（`SyncStep_config.xml`、`SyncTable.properties`） |
| `dmm\` | 資料模型定義（DataTypeDefXSD.xml） |

### 5.2 功能模組（由 hibernate 設定檔推知）

| 目錄 | 模組 |
|---|---|
| `conf\iso\` | ISO 文件管理 |
| `conf\dt\` | DT Module |
| `conf\mpt\` | MPT / ECP Module |
| `conf\mts\` | MTS Module |
| `conf\epm\` | 費用管理（Expense）+ ERP 整合 |

### 5.3 執行期資料

| 路徑 | 內容 |
|---|---|
| `modules\NaNa\DocServer\document\attachment\` | 附件檔案庫 |
| `modules\NaNa\DocServer\document\ISO\`、`ISOSOURCE\` | ISO 文件本體 |
| `modules\NaNa\index\` | Lucene 全文檢索索引 |
| `modules\NaNa\ResourceBundle\BPMRsrcBundle.xlsx` | 多語系詞彙表（1.8MB） |
| `bin\NaNaDocuments\` | 表單附件（檔名為 hash） |
| `bin\NaNaDrafts\` | 草稿 |
| `bin\NaNaImages\` | 表單圖片 |
| `bin\NaNaPreferences\` | 使用者偏好設定 XML |

### 5.4 客製邏輯所在（上層目錄 `D:\檔案分享\BPM\`）

這裡才是貴公司自己的東西：

- `*.form` → `com.dsc.nana.domain.form.FormDefinition` 的 XML 序列化，即**表單定義**
- `ISOMod.js` → 掛在表單上的**客製 JavaScript**（ISO 文件變更單），透過 DWR 呼叫後端 `ajax_OrgAccessor`、`ajax_DatabaseAccessor`、`ajax_IsoModuleAccessor`、`ajax_CustomModuleAccessor` 等介面
- `資料庫結構\` → 資料庫 schema 說明
- `借貨單\`、`廠內異常單\`、`環安\`、`禾迅_資訊設備申請\`、`BPMISO\`、`APITest\` → 各流程的客製檔案

> **重要：真正的流程圖、關卡、簽核規則不在檔案系統，全部存在資料庫裡。**

---

## 六、Log 分析

`modules\NaNa\log\` 共 **5,285 個檔案 / 65.48 GB**，每天輪替，單日約 450MB。

| 日誌名稱 | 檔數 | 用途 |
|---|---|---|
| `NaNaWeb.log.*` | 161 | Web 層 |
| `Tiptop.log.*` | 161 | TIPTOP ERP 整合 |
| `NaNaApp.log.*` | 161 | 應用層（含 stack trace） |
| `NaNaSecurity.log.*` | 45 | 安全稽核 |
| `NaNaLogin.log.*` | 44 | 登入記錄 |
| `MobileWeb.log.*` | 31 | 行動版 |
| `NaNaValidate.log.*` | 27 | 驗證 |
| `AppForm.log.*` | 27 | 表單應用 |
| `BPMMPT.log.*` | 6 | MPT 模組 |
| `SyncISODocument-*` | 多筆 | ISO 文件同步 |

在無原始碼的情況下，**log 中的 stack trace 是反推系統行為最有效的來源**。

### 6.1 爆量根因

`NaNaApp.log` 一項就佔 64.97 GB（全部日誌的 99.2%），內容幾乎全是同一個錯誤的 stack trace：

```
ERROR [DefaultFileServiceImpl.getFileDirectly:635] Fail to get file named '...'
java.io.FileNotFoundException
```

抽樣單一日誌檔的前 30 萬行，即出現 **2,843 次 `FileNotFoundException`**。系統反覆嘗試讀取 DocServer 中已不存在的附件，每次都輸出完整 stack trace。

各月成長量：

| 月份 | 檔數 | 容量 | 單日均 |
|---|---|---|---|
| 2026-04 | 30 | 13.33 GB | 455 MB |
| 2026-05 | 31 | 10.62 GB | 351 MB |
| 2026-06 | 30 | 10.24 GB | 349 MB |
| 2026-07 | 31 | 13.68 GB | 452 MB |
| 2026-08 | 31 | 13.61 GB | 449 MB |
| 2026-09 | 8 | 3.50 GB | 449 MB |

超過 180 天的舊檔全部加總僅 0.03 GB，代表**爆量始於 2026-03-11 的版更**（與設定檔中「版更工具自動遷移 2026-03-11」的註記時間吻合）。

### 6.2 清理記錄（2026-09-07）

| 項目 | 之前 | 之後 |
|---|---|---|
| log 資料夾 | 65.48 GB | 478 MB |
| D: 剩餘空間 | 72.9 GB | 137.9 GB |
| D: 使用率 | 64.3% | 32.4% |

- **刪除** 567 個輪替檔（NaNaApp 160、Tiptop 160、NaNaWeb 160、MobileWeb 30、NaNaValidate 26、AppForm 26、BPMMPT 5）
- **保留** 261 個檔：13 個作用中日誌、89 個 NaNaSecurity / NaNaLogin 稽核輪替檔、syncorg 同步記錄
- 未修改任何設定檔（本目錄為測試區複製品，改動不會回套）

> 注意：清理當日的 `NaNaApp.log` 已達 435 MB，錯誤迴圈仍在以每日約 450 MB 的速度寫入。若正式區使用同一組附件資料，該主機磁碟會以相同速度被消耗。

---

## 七、發現的問題

### 7.1 明文憑證（高）

- `modules\NaNa\conf\epm\ERP.hibernate.cfg.xml`
  含 **TIPTOP ERP 正式資料庫的連線位址、帳號與密碼（明文）**。
- `modules\NaNa\DocServer\document\.env`
  含**明文 API_KEY**，對應同目錄下自建的 `FileAPI.exe`（監聽 Port 5144，CORS 允許 `10.10.130.122:5149`）。
- `standalone\configuration\standalone-full.xml`
  **5 組 datasource 全部使用 `sa` 帳號**（MSSQL `10.10.130.191:1433`），密碼以 `<password>` 明文儲存，**未使用 WildFly Vault 加密**。

  | Pool | 資料庫 |
  |---|---|
  | `NaNaDS` | NaNa（主庫） |
  | `NaNaCustDS` | NaNa（客製） |
  | `ProcessArchiveDS` | NaNabackup（流程封存） |
  | `BPMMPT` | NaNa |
  | `ExampleDS` | H2 記憶體庫（WildFly 預設，未使用） |

> 此份拷貝放在檔案分享區，等同於這些憑證已對所有能存取該分享的人公開。建議優先處理。
> 另外，以 `sa`（SQL Server 最高權限帳號）跑應用程式本身就不符合最小權限原則，建議改用專用帳號。

### 7.2 排程錯誤持續累積（中）

`NaNaApp.log` 每日固定出現：

```
ERROR [TimerFacadeBean.executeApp:158] [...-appId-APP16607030043841]
ApplicationDefinition cannot be found.
com.dsc.nana.persistence.ObjectNotFoundException:
  Cannot find Object by query command: select o from ApplicationDefinition o
  where (o.id = 'APP16607030043841')
```

推測是該應用定義已被刪除，但 Quartz 排程未一併清除。

### 7.3 Log 無保留上限（中）

log 只做每日輪替、未設保留天數，半年累積 65GB。測試區已於 2026-09-07 手動清理，但**根因（7.4）未解且未設 retention**，約 5 個月後會再次塞滿。

正式區若要處理，需修改 `modules\NaNa\conf\NaNaLog.properties` 設定保留天數，並重啟服務。

### 7.4 附件遺失導致錯誤迴圈（高，根因）

`DefaultFileServiceImpl.getFileDirectly` 持續拋出 `java.io.FileNotFoundException`，即 DocServer 中的附件檔案已不存在，但資料庫仍有對應記錄。

此問題有兩層影響：

1. **日誌爆量** — 每日約 450 MB 純 stack trace（即第六節的 65GB 來源）
2. **功能面** — 使用者實際開啟這些表單附件時應該也是失敗的，屬於資料完整性問題

建議從 log 撈出所有 `Fail to get file named '...'` 的檔名清單，比對 DocServer 與資料庫，確認是附件遺失、路徑變更，或與自建的 `FileAPI.exe` 遷移有關。

### 7.5 非標準設定由版更工具遷移（低）

多個 properties 檔尾端有此註記：

```
# 以下為非標準設定，由版更工具自動遷移 2026-03-11 10:27:51
```

代表 2026-03-11 曾做過版本更新，且系統存在人工加入的非標準設定，升級時需留意。

---

## 八、後續建議方向

| 方向 | 說明 |
|---|---|
| **A. 客製流程邏輯** | 深入 `D:\檔案分享\BPM\` 的 `.form` 檔與客製 JS，這是公司自有的業務邏輯 |
| **B. 資料庫結構** | 從 `資料庫結構\` 反推流程定義、關卡、表單資料如何儲存——BPM 的核心邏輯都在 DB |
| **C. 取得完整部署** | ✅ **已完成**（2026-09-07 補上 `standalone\`，見第九節） |
| **D. Log 反推** | 用 stack trace 建立系統行為與類別關係圖 |
| **E. 前端原始碼** | `NaNaWeb.war` 的 565 個 JSP 與 1,423 個 JS 完全可讀，是理解系統行為最直接的入口 |

---

## 九、應用程式本體（standalone\deployments）

2026-09-07 補上，共 **12 個部署單元 / 1.1 GB**，全部處於已部署狀態。

| 部署單元 | 大小 | 狀態 | 推測用途 |
|---|---|---|---|
| `NaNaWeb.war` | 422 MB | 已部署 | **主 Web 應用**（唯一以解壓縮目錄形式存在，可直接讀寫） |
| `NaNaXWeb.war` | 137 MB | 已部署 | 新版前端（4,805 js + 72 ts） |
| `MTSModule.war` | 109 MB | 已部署 | MTS 模組 |
| `BPMMPT.war` | 96 MB | 已部署 | MPT / ECP 模組 |
| `ISOModule.war` | 83 MB | 已部署 | ISO 文件管理 |
| `UExpense.war` | 49 MB | 已部署 | 費用申請 |
| `nana-app.ear` | 83 MB | 已部署 | **核心商業邏輯**（內含 134 個 jar） |
| `BPMFullTextSearch.ear` | 45 MB | 已部署 | 全文檢索 |
| `BPMiReports.ear` | 36 MB | 已部署 | 報表（iReport / JasperReports） |
| `nana-process-archive.ear` | 19 MB | 已部署 | 流程封存 |
| `BPMSecudocx.ear` | 9 MB | 已部署 | 文件保全 |
| `zEARforNotice.ear` | 12 KB | 已部署 | 通知 |

### 9.1 NaNaWeb.war 結構（展開目錄，8,256 檔）

主要功能目錄：`BPMModule`、`ISOModule`、`CriticalModule`、`EBGModule`、`TFAModule`（雙因素驗證）、`WMS`、`CustomModule`、`CustomJsLib`、`CustomCssLib`、`CustomMultilanguage`、`OpenWin`、`Document`、`app`

`WEB-INF\` 重點檔案：

| 檔案 | 用途 |
|---|---|
| `struts-common-config.xml`（17.6 KB） | **Struts action 對應表——所有 URL 到後端類別的路由都在這** |
| `struts-openWin-config.xml` | 彈出視窗路由 |
| `dwr-default.xml`（12.8 KB） | **DWR 開放給前端呼叫的後端類別白名單** |
| `server-config.wsdd` | Axis Web Service 端點定義 |
| `jboss-deployment-structure.xml` | 模組相依（含對 `NaNa` module 的引用） |
| `portlet.xml` / `liferay-portlet.xml` | Liferay 入口網站整合 |

> `struts-common-config.xml` 與 `dwr-default.xml` 這兩支是理解系統架構的最佳起點——前者列出所有 Web 進入點，後者列出所有前端可直呼的後端服務。

### 9.2 待處理項目

`BPMDT.war.dodeploy` 標記檔存在，但**對應的 `BPMDT.war` 不存在**。這是 2025-02-13 留下的孤兒標記，WildFly 啟動時會嘗試部署一個不存在的檔案。`modules\NaNa\conf\dt\` 有對應的 DT 模組設定，推測該模組後來被移除但標記檔未清。
