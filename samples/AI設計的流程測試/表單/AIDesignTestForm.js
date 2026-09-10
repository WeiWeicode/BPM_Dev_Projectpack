// ============================================================
// AI設計的流程測試 — 表單腳本
// 表單 ID：AIDesignTestForm
// 流程   ：AIDesignTestProcess（開單人 → 直屬主管 → 結案）
//
// 可用資源依據：BPM5892/BPM_表單腳本可用資源.md
//   - jQuery / DWR engine / FormUtil / OpenWin 等皆已由表單頁預載，不要重複載入
//   - 只額外載入組織查詢服務 ajax_OrgAccessor
// ============================================================

// 組織／人員查詢（DWR 動態產生，檔案總管找不到但 URL 載得到）
document.write(
  '<script type="text/javascript" src="../../dwrDefault/interface/ajax_OrgAccessor.js"></script>'
);

// ------------------------------------------------------------
// 生命週期
// ------------------------------------------------------------
function formCreate() {
  return true;
}

function formOpen() {
  initForm();
  return true;
}

function formSave() {
  return checkRequired();
}

function formClose() {
  return true;
}

function formDispatch() {
  return true;
}

// ------------------------------------------------------------
// 初始化
// ------------------------------------------------------------
function initForm() {
  // 隱藏欄位：記下流程實例 ID，方便日後對帳
  FormUtil.setValue("processInstOIDHidden", [processInstOID]);

  // 開單關卡第一次進來時，自動帶入申請人與部門
  if (activityId === "ApplyUserTask" && !FormUtil.getValue("EmpDialogInputLabel")[0]) {
    fillApplicant();
  }

  // 依申請類別決定備註欄要不要顯示
  CategoryDropDown_onchange();
}

// ------------------------------------------------------------
// 按鈕：帶入部門與人員
//   工號／姓名 取自表單執行期全域變數（userId / userName，已在正式表單驗證過）
//   部門則透過 DWR 的 ajax_OrgAccessor.findCurrentUser 取得
// ------------------------------------------------------------
function PickUserButton_onclick() {
  fillApplicant();
}

function fillApplicant() {
  // 雙輸入框：第一格工號、第二格姓名
  FormUtil.setValue("EmpDialogInputLabel", [userId, userName]);

  if (typeof ajax_OrgAccessor === "undefined") {
    alert("組織查詢服務 ajax_OrgAccessor 未載入，部門欄位請手動填寫。");
    return;
  }

  ajax_OrgAccessor.findCurrentUser(function (user) {
    if (!user) {
      alert("查不到目前登入者的組織資料，部門欄位請手動填寫。");
      return;
    }

    // 各站台的欄位命名不一定相同，這裡列出常見幾種；都對不上就把原始物件印出來，
    // 不猜、也不靜默略過（見 AGENTS.md 第 6 節）
    var deptId =
      user.orgUnitId || user.deptId || user.organizationUnitId || user.orgId || "";
    var deptName =
      user.orgUnitName || user.deptName || user.organizationUnitName || user.orgName || "";

    if (!deptId && !deptName) {
      console.log("ajax_OrgAccessor.findCurrentUser 回傳內容：", user);
      alert(
        "取得使用者資料成功，但部門欄位名稱與預期不同。\n" +
          "請開 F12 主控台看「findCurrentUser 回傳內容」，再把 fillApplicant() 裡的欄位名稱改成正確的。"
      );
      return;
    }

    // 雙輸入框：第一格部門代號、第二格部門名稱
    FormUtil.setValue("DeptDoubleTextBox", [deptId, deptName]);
  });
}

// ------------------------------------------------------------
// 按鈕：檔案上傳
//   附件走 BPM 內建的附件區元件（Attachment），這顆按鈕只負責把畫面捲過去。
// ------------------------------------------------------------
function UploadFileButton_onclick() {
  var box = document.getElementById("Attachment");
  if (!box) {
    alert("找不到附件區元件（Attachment），請確認表單版面是否包含附件區。");
    return;
  }
  FormUtil.show(["Attachment"]);
  box.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------
// 明細表格（ItemGrid）
//   欄位繫結到 ItemNoTextBox / ItemNameTextBox / ItemQtyTextBox 三個輸入元件：
//   先在上方欄位輸入，再按表格的「新增」把該列加進表格。
// ------------------------------------------------------------
function ItemGrid_add_onclick() {
  if (!FormUtil.getValue("ItemNameTextBox")[0]) {
    alert("請先輸入品名，再按新增。");
    return false;
  }
  ItemGridObj.addRow();
  ItemGridObj.clearBinding();
  return true;
}

function ItemGrid_edit_onclick() {
  ItemGridObj.editRow();
  ItemGridObj.clearBinding();
  return true;
}

function ItemGrid_delete_onclick() {
  ItemGridObj.deleteRow();
  ItemGridObj.clearBinding();
  return true;
}

// ------------------------------------------------------------
// 欄位連動
// ------------------------------------------------------------
function CategoryDropDown_onchange() {
  // 示範欄位連動：只有選「其他」時才要求填相關單號
  var v = FormUtil.getValue("CategoryDropDown")[0];
  if (v === "其他") {
    FormUtil.show(["RelatedNoDialogInput"]);
  } else {
    FormUtil.setValue("RelatedNoDialogInput", [""]);
    FormUtil.hide(["RelatedNoDialogInput"]);
  }
}

// ------------------------------------------------------------
// 送出前檢查
// ------------------------------------------------------------
function checkRequired() {
  // 只在開單關卡檢查；主管關卡多數欄位是唯讀的
  if (activityId !== "ApplyUserTask") {
    return true;
  }

  var required = {
    主旨: FormUtil.getValue("SubjectTextBox")[0],
    內容說明: FormUtil.getValue("ContentTextArea")[0],
    申請人: FormUtil.getValue("EmpDialogInputLabel")[0],
    需求日期: FormUtil.getValue("NeedDate")[0],
  };

  var msg = "";
  for (var key in required) {
    if (!required[key]) {
      msg += "  " + key + "\n";
    }
  }

  if (msg !== "") {
    alert("以下欄位為必填，請填寫後再送出：\n" + msg);
    return false;
  }
  return true;
}
