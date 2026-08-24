<script setup lang="ts">
import { inject } from 'vue';

const showToast = inject<(msg: string) => void>('showToast', () => {});

function copyText(text: string, label: string) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`已複製 ${label}`);
  });
}

const envelopeExample = `<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <ns1:findFormOIDsOfProcess xmlns:ns1="http://webservice.nana.dsc.com/">
      <pProcessPackageId xsi:type="xsd:string">SP_DetectionOPProcess</pProcessPackageId>
    </ns1:findFormOIDsOfProcess>
  </soapenv:Body>
</soapenv:Envelope>`;

const formFieldExample = `<SP_DetectionOPForm>
  <EmailSubjectTextBox id="EmailSubjectTextBox" dataType="java.lang.String" perDataProId="">主旨</EmailSubjectTextBox>
  <ControlPlanApplyDate id="ControlPlanApplyDate" dataType="java.util.Date">2026/08/24</ControlPlanApplyDate>
</SP_DetectionOPForm>`;
</script>

<template>
  <div class="guide-container">
    <div class="guide-header">
      <h2>📖 呼叫 BPM WorkflowService 前必讀指南</h2>
      <p class="guide-subtitle">
        鼎新 NaNaWeb 的 WorkflowService 服務底層為 Apache Axis 1.3，具有許多非現代 SOAP 的特殊行為與設計陷阱。
      </p>
    </div>

    <!-- 1. rpc/encoded -->
    <div class="guide-card">
      <div class="card-badge">重點 ①</div>
      <h3 class="card-title">這是 rpc/encoded，不是 document/literal</h3>
      <p>
        此服務由 Apache Axis 1.3 產生，採用早期 SOAP 標準風格。實務開發上有三個關鍵特點：
      </p>
      <ul class="guide-list">
        <li>
          <b>參數為位置對應 (parameterOrder)</b>：順序錯了不會報錯，只會拿到錯的結果或空值。本工具已自動依 WSDL 宣告順序封裝。
        </li>
        <li>
          <b><code>SOAPAction</code> 為空字串</b>：請求路由分派完全依照 body 內的方法名稱標籤。
        </li>
        <li>
          <b>Python 函式庫相容性</b>：Python 的 <code>zeep</code> 明確不支援 SOAP encoding；本專案採用 <code>ws_client.py</code> 手刻 Envelope。Node 端的 <code>soap</code> 套件可直接相容。
        </li>
      </ul>

      <div class="code-wrapper">
        <div class="code-header">
          <span>標準 SOAP Envelope 格式</span>
          <button class="copy-btn-inline" @click="copyText(envelopeExample, 'SOAP Envelope 範本')">複製範本</button>
        </div>
        <pre class="code-box"><code>{{ envelopeExample }}</code></pre>
      </div>
    </div>

    <!-- 2. 回傳 string 多重型態 -->
    <div class="guide-card">
      <div class="card-badge">重點 ②</div>
      <h3 class="card-title">回傳的 string 幾乎都不是純字串</h3>
      <p>
        65 支方法中有 41 支宣告回傳 <code>string</code>，但其真實內容分為以下四種，WSDL 規格層面完全看不出來：
      </p>

      <table class="data-table">
        <thead>
          <tr>
            <th>實際內容型態</th>
            <th>代表性方法</th>
            <th>解析方式與注意事項</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>XStream 序列化 Java 物件 XML</b></td>
            <td><code>fetchProcInstances</code>、<code>fetchOrgUnitOfUserId</code></td>
            <td>最常見型態。包含 <code>PersistentSet</code>、<code>SET__PROXY__CLASS__NAME</code> 等 Hibernate 代理雜訊。</td>
          </tr>
          <tr>
            <td><b>屬性式 XML</b></td>
            <td><code>getSubstituteState</code></td>
            <td>風格與 XStream 不同，多以屬性表示欄位值。</td>
          </tr>
          <tr>
            <td><b>逗號分隔字串</b></td>
            <td><code>fetchCanTraceProcSN</code></td>
            <td>例如 <code>SN001,SN002,SN003</code>，需手動 split(',')。</td>
          </tr>
          <tr>
            <td><b>純量文字</b></td>
            <td><code>findFormOIDsOfProcess</code>、<code>fetchProcessContextVariable</code></td>
            <td>單一 32 碼 OID 或純文字變數值。</td>
          </tr>
        </tbody>
      </table>

      <div class="callout info" style="margin-top: 12px;">
        <div class="callout-title">💡 表單資料雙層解包提醒</div>
        <div>
          <code>fetchFormInstance*</code> 更是「XML 字串包在 XML 裡」，其 <code>fieldValues</code> 節點本身是一段需要進行第二次 XML 解析的跳脫字串。
        </div>
      </div>
    </div>

    <!-- 3. 失敗有三種與假成功 -->
    <div class="guide-card">
      <div class="card-badge">重點 ③</div>
      <h3 class="card-title">失敗有三種，其中一種不會丟例外（假成功 soft_error）</h3>
      <p>
        呼叫服務失敗時，不可只依賴 HTTP 狀態碼或 SOAP Fault 判斷：
      </p>

      <table class="data-table">
        <thead>
          <tr>
            <th>錯誤型態</th>
            <th>HTTP 狀態與表現</th>
            <th>呼叫端正確處理方式</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>SOAP Fault</b></td>
            <td>HTTP 500，<code>faultstring</code> 帶 Java 例外堆疊</td>
            <td>標準 SOAP 例外攔截。</td>
          </tr>
          <tr>
            <td><b>業務性拒絕</b></td>
            <td>HTTP 500，訊息明確（如「單子在跑，無作廢意見」）</td>
            <td>讀取 <code>faultstring</code> 文字，不要當成系統崩潰。</td>
          </tr>
          <tr>
            <td><b style="color: #d46b08;">假成功 (Soft Error)</b></td>
            <td><b>HTTP 200，但回傳字串是 <code>&lt;NotFoundException&gt;...&lt;/NotFoundException&gt;</code></b></td>
            <td><b>必須額外檢查回傳內容是否包含 Exception 標籤</b>。目前已知 <code>findManagerByAppLvl</code> 有此行為。</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 4. pFormFieldValue 格式 -->
    <div class="guide-card">
      <div class="card-badge">重點 ④</div>
      <h3 class="card-title">表單欄位值 (pFormFieldValue) 的 XML 結構</h3>
      <p>
        開單或回寫表單資料時，<code>pFormFieldValue</code> 需為以表單 ID 為根節點的 XML 字串，每個欄位對應一個標籤：
      </p>

      <div class="code-wrapper">
        <div class="code-header">
          <span>pFormFieldValue 標準格式範例</span>
          <button class="copy-btn-inline" @click="copyText(formFieldExample, 'pFormFieldValue 範本')">複製範本</button>
        </div>
        <pre class="code-box"><code>{{ formFieldExample }}</code></pre>
      </div>
      <p class="guide-tip">
        存入後由 <code>fetchFormInstance*</code> 讀出時亦為此結構，來回完全對稱一致。
      </p>
    </div>

    <!-- 5. 錯的欄位 ID 延後爆炸地雷 -->
    <div class="guide-card danger-card">
      <div class="card-badge danger">重點 ⑤</div>
      <h3 class="card-title">💣 已知地雷：錯的欄位 ID 不會被擋，會延後爆炸</h3>
      <p>
        <code>invokeProcess</code> <b>不會驗證</b> <code>pFormFieldValue</code> 裡的欄位 ID 是否真實存在於表單定義中。
      </p>
      <div class="callout danger">
        <div class="callout-title">延後爆炸現象</div>
        <div>
          不存在的欄位照樣寫進單據，開單回傳 200 成功。等到後續有人呼叫 <code>fetchUniFormatFormInstanceWithProcSerlNo</code> 讀取該單時，服務端才會拋出 <code>IllegalArgumentException: Argument 'pFieldId = xxx' cannot find ElementDefinition</code> 崩潰。而一般的 <code>fetchFormInstanceWithProcSerlNo</code> 讀同一張單卻不會報錯，因此容易被忽略。
        </div>
      </div>
      <div class="solution-box">
        <b>🛡️ 最佳實務防範方案：</b><br />
        在組裝 <code>pFormFieldValue</code> 開單前，一律先呼叫 <code>getFormFieldTemplate(pFormDefOID)</code> 取得權威欄位 ID 清單進行校驗對齊。
      </div>
    </div>
  </div>
</template>

<style scoped>
.guide-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
  max-width: 960px;
  margin: 0 auto;
}

.guide-header {
  margin-bottom: 28px;
}
.guide-header h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
  color: var(--text);
}
.guide-subtitle {
  margin: 0;
  color: var(--text-dim);
  font-size: 14px;
}

.guide-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  position: relative;
}
.guide-card.danger-card {
  border-color: #ffccc7;
  background: #fffafa;
}

.card-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  margin-bottom: 8px;
}
.card-badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.card-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: var(--text);
}

.guide-list {
  padding-left: 20px;
  margin: 12px 0;
  color: var(--text);
  line-height: 1.7;
}
.guide-list li {
  margin-bottom: 8px;
}

.code-wrapper {
  margin-top: 14px;
}
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
}
.copy-btn-inline {
  font-size: 11px;
  padding: 2px 8px;
}

.guide-tip {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 8px;
}

.solution-box {
  margin-top: 12px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  color: #237804;
  font-size: 13px;
  line-height: 1.6;
}
</style>
