document.write(
  '<script type="text/javascript" src="../../CustomJsLib/EFGPShareMethod.js"></script>'
); //for 開窗
document.write(
  '<script type="text/javascript" src="../../dwrDefault/interface/ajax_DatabaseAccessor.js"></script>'
); //連資料庫
document.write(
  '<script type="text/javascript" src="../../js/CustomDataChooser.js"></script>'
);

// 寫入資料庫
document.write(
  '<script type="text/javascript" src="../../dwrDefault/interface/ajax_DatabaseAccessor.js"></script>'
);

// axios 後端資料傳輸
document.write(
  '<script src="http://10.10.130.122:5148/modules/axios/dist/axios.min.js"></script>'
);

// 引用iframe
document.write(
  '<script src="http://10.10.130.122:5148/modules/iframe-resizer/js/iframeResizer.js"></script>'
);

function formCreate() {
  return true;
}
function formOpen() {
  showUtil();
  openSetValue();
  openSet();

  return true;
}
function formSave() {
  afterFormSave();
  return nullAlert();
}

function formClose() {
  return true;
}
function formDispatch() {
  return true;
}

// showUtil
function showUtil() {
  FormUtil.hide(["TestButton"]);
}

// 打開設定
function openSet() {
  //初始化Grid元件轉成Dialog操作模式
  FormUtil.transToDialog({
    gridId: "openExtraDataDialog", // 自行命名抽屜ID
    inputId: "ExtraDataSubTab", // 輸入元件擺放的「分頁元件」代號
  });

  FormUtil.transToDialog({
    gridId: "ReminderNoteImageDialog", // 自行命名抽屜ID
    inputId: "ReminderNoteImageSubTab", // 輸入元件擺放的「分頁元件」代號
  });

  // 轉換iframe套件
  ViewChangeIframe("ECContentDescAttTextArea", "太陽能ECRECN_內容說明");
  ViewChangeIframe("ECSpecAttTextArea", "太陽能ECRECN_規格");
}

// 打開設定值
function openSetValue() {
  // 取得id="BPMBackFormId"的元素
  let SerialNumberID = FormUtil.getValue("SerialNumber")[0];

  // if GSRNFormID.value如果為空值就給formId (只有第一次會執行)
  if (SerialNumberID == "") {
    // 建立單號 年月日時分秒毫秒
    let date = new Date();
    let year = date.getFullYear();
    let month = date.getMonth() + 1;
    let day = date.getDate();
    let hh = date.getHours();
    let mm = date.getMinutes();
    let ss = date.getSeconds();
    let ms = date.getMilliseconds();

    // 組合字串
    let formId =
      year + "" + month + "" + day + "" + hh + "" + mm + "" + ss + "" + ms;

    axios.get("http://10.10.130.122:5123/v1/api/nanoid/generate").then((response) => {
      const randomId = response.data.data.id;
      let GSRNFormIDValue = processId + "_" + userId + "_" + formId + "_" + randomId;
      FormUtil.setValue("BPMBackFormIdHidden", [GSRNFormIDValue]);
      // 轉換iframe套件
      ViewChangeIframe("ECContentDescAttTextArea", "太陽能ECRECN_內容說明");
      ViewChangeIframe("ECSpecAttTextArea", "太陽能ECRECN_規格");
    });

  }

  // 設定表單實例ID
  FormUtil.setValue("formInstOIDHidden", [formInstOID]);
  // 設定流程實例ID
  FormUtil.setValue("processInstOIDHidden", [processInstOID]);

  ChgItemDropDown_onchange();
  ProductCategoryDropDown_onchange();
  UseMachineDropDown_onchange();
}

// 儲存後設定值
function afterFormSave() {
  if (activityId == "ECRConfirmUserTask" && workItemSource == "0") {
    FormUtil.setValue("ECRNoTextBox", [
      "ECR_" + FormUtil.getValue("SerialNumber")[0],
    ]);
  }
  if (activityId == "ECNConfirmUserTask" && workItemSource == "0") {
    FormUtil.setValue("ECNNoTextBox", [
      "ECN_" + FormUtil.getValue("SerialNumber")[0],
    ]);
  }
  let today = new Date();
  const ApprovalRecordTextBoxValue =
    today.toLocaleString() + "，由 " + userName + " 確認";

  // 活動代號,設定欄位
  const setApprovalValue = {
    ERBS2100UserTask: "ERBS2100ApprovalRecordTextBox",
    ERBS2190UserTask: "ERBS2190ApprovalRecordTextBox",
    ERBS3100UserTask: "ERBS3100ApprovalRecordTextBox",
    ERBS4210UserTask: "ERBS4210ApprovalRecordTextBox",
    ERBS4230UserTask: "ERBS4230ApprovalRecordTextBox",
    ERBS6100UserTask: "ERBS6100ApprovalRecordTextBox",
  };
  if (activityId in setApprovalValue) {
    const targetField = setApprovalValue[activityId];
    const existingValue = FormUtil.getValue(targetField)[0];
    const newValue = ApprovalRecordTextBoxValue;
    FormUtil.setValue(targetField, [newValue]);
    // if (!existingValue.includes(userName)) {
    //   const newValue = existingValue
    //     ? existingValue + "\n" + ApprovalRecordTextBoxValue
    //     : ApprovalRecordTextBoxValue;
    //   FormUtil.setValue(targetField, [newValue]);
    // }
  }
}


function nullAlert() {
  let msg = "";

  let tempJsonValue = {
    變更屬性: FormUtil.getValue("ChgPropertyRadio")[0],
    變更項目: FormUtil.getValue("ChgItemDropDown")[0],
    產品種類: FormUtil.getValue("ProductCategoryDropDown")[0],
    上線時間: FormUtil.getValue("OnlineDate")[0],
    上線機台: FormUtil.getValue("UseMachineDropDown")[0],
    測試放量: FormUtil.getValue("TestQtyTextBox")[0],
    主旨: FormUtil.getValue("ECSubjectTextBox")[0],
    內容說明: FormUtil.getValue("ECContentDescTextArea")[0],
    規格: FormUtil.getValue("ECSpecTextArea")[0]

  };


  // 查看tempJsonValue欄位為空值 如果為空值就加入msg
  for (const [key, value] of Object.entries(tempJsonValue)) {
    if (!value) {
      msg += `'${key}'\n`;
    }
  }



  const targetPrefixes = ["ERBS2190", "ERBS3100", "ERBS4210", "ERBS6100", "ERBS4230", "ERBS2100"];
  const prefix = targetPrefixes.find(p => activityId === `${p}UserTask`);
  if (prefix) {
    if (FormUtil.getValue(`${prefix}PrecautionsRadio`)[0] == undefined && FormUtil.getValue(`${prefix}OtherRadio`)[0] == undefined) {
      msg += "請選取欄位注意事項與其他";
    }
  }

  if (msg != "") {
    alert(`以下欄位為空值，請填寫後送出：\n ` + msg);
    return false;
  } else {
    return true;
  }

}

/* 按鈕事件 */

// 開啟補充資料視窗
function ExtraDataAddOpenButton_onclick() {
  ExtraDataGridObj.clearBinding(); //清空資料

  // http://10.10.130.122:5124/sql-files
  
  // 使用axios取得資料
  axios
    .get("http://10.10.130.122:5124/sql-files")
    .then((response) => {
      let getfiles;
      // 查詢response.data.files.sourceNumber等於BPMBackFormIdHidden的值
      const BPMBackFormIdHiddenValue = FormUtil.getValue(
        "BPMBackFormIdHidden"
      )[0];
      getfiles = response.data.files.filter(
        (file) => file.sourceNumber === BPMBackFormIdHiddenValue
      );
      try {
        
        // console.log(getfiles);

        // 設定DropdownID=ExtraDataAttDropDown 將originalName放入選項
        // FormUtil.setOption("<DropdownID>",[{"text":"A","value":"1"},{"text":"B","value":"2"}]);
        const changFileNameToDropdown = getfiles.map((file) => ({
          text: file.originalName,
          value: file.originalName,
        }));
        // console.log(changFileNameToDropdown);

        // 取得ExtraDataAttDropDown下拉選單的值
        const selectElement = document.getElementById("ExtraDataAttDropDown");
        // 清空下拉選單
        selectElement.innerHTML = "";
        // 新增預設選項
        const defaultOption = document.createElement("option");
        defaultOption.text = "";
        defaultOption.value = "";
        selectElement.add(defaultOption);
        // 將檔案名稱加入下拉選單
        changFileNameToDropdown.forEach((file) => {
          const option = document.createElement("option");
          option.text = file.text;
          option.value = file.value;
          selectElement.add(option);
        });
        
      } catch (error) {
        console.error("Error parsing JSON:", error);
      }

      // console.log(getfiles);
    })
    .catch((error) => {
      console.error("Error fetching files:", error);
    });

  let today = new Date();
  FormUtil.setValue("ExtraDataSetupTimeTextBox", [today.toLocaleString()]);
  FormUtil.setValue("ExtraDataWorkNumberTextBox", [userId]);
  FormUtil.setValue("ExtraDataWorkNameTextBox", [userName]);

  FormUtil.showGridDialog("openExtraDataDialog");
}

// 新增補充資料
function ExtraDataAddButton_onclick() {
  if (true) {
    //
    FormUtil.hideGridDialog("openExtraDataDialog");

    ExtraDataGridObj.addRow();
    ExtraDataGridObj.clearBinding();
    return true;
  } else {
    return false;
  }
}

function ExtraDataDelButton_onclick() {
  if (true) {
    ExtraDataGridObj.deleteRow();
    ExtraDataGridObj.clearBinding();
    return true;
  } else {
    return false;
  }
}

function ChgItemDropDown_onchange() {
  const ChgItemDropDownValue = FormUtil.getValue("ChgItemDropDown")[0];

  if (ChgItemDropDownValue === "其他") {
    FormUtil.show(["ChgItemOtherTextArea"]);
  } else {
    FormUtil.setValue("ChgItemOtherTextArea", [""]);
    FormUtil.hide(["ChgItemOtherTextArea"]);
  }
}
function ProductCategoryDropDown_onchange() {
  const ProductCategoryDropDownValue = FormUtil.getValue(
    "ProductCategoryDropDown"
  )[0];

  if (ProductCategoryDropDownValue === "其他") {
    FormUtil.show(["ProductCategoryOtherTextArea"]);
  } else {
    FormUtil.setValue("ProductCategoryOtherTextArea", [""]);
    FormUtil.hide(["ProductCategoryOtherTextArea"]);
  }
}
function UseMachineDropDown_onchange() {
  const UseMachineDropDownValue = FormUtil.getValue("UseMachineDropDown")[0];

  if (UseMachineDropDownValue === "其他") {
    FormUtil.show(["UseMachineOtherTextArea"]);
  } else {
    FormUtil.setValue("UseMachineOtherTextArea", [""]);
    FormUtil.hide(["UseMachineOtherTextArea"]);
  }
}

function ChangeItemImgButton_onclick() {
  FormUtil.showGridDialog("ReminderNoteImageDialog");
}

// AttButton_onclick
function AttButton_onclick() {
  const roleValue = "edit";
  const filterValue = "查詢全部";
  const url = uploadURL(roleValue, filterValue);
  // 開窗 不要顯示網址 不要顯示工具列
  window.open(url, "_blank", "toolbar=no,location=no");
}

// TestButton_onclick
function TestButton_onclick() {}

// 上傳附件套件
function uploadURL(roleValue, filterValue) {
  // EX:http://10.10.130.122:5147/GigaSolarBPM/FileUpload/MIS反應單/PO20250711/S112009/BPM/edit/報修單|User上傳|User資料/MIS反應單_報修單
  // FileUpload/:sourceApplication/:sourceNumber/:userNumber/:platform/:role/:class/:filter

  // URL主機
  const host = "http://10.10.130.122:5147/GigaSolarBPM/FileUpload/";
  // 參數
  // 來源應用
  const sourceApplication = "太陽能ECRECN"; // 系統名稱
  const sourceNumber = FormUtil.getValue("BPMBackFormIdHidden")[0]; // 來源單號
  const userNumber = userId; // 使用者工號
  const platform = "BPM"; // 平台
  const role = roleValue; // 角色
  const className = ["內容說明", "規格"]; // 類別
  const filter = filterValue; // 篩選條件

  // 組合完整的上傳URL
  const uploadURL = `${host}${sourceApplication}/${sourceNumber}/${userNumber}/${platform}/${role}/${className.join(
    "|"
  )}/${filter}`;

  // console.log("上傳URL:", uploadURL);
  return uploadURL;
}

// 其他補充function
// 將網頁元件id替換成 iframe
function ViewChangeIframe(changeHtmlId, filter) {
  // iframe網址
  //  http://10.10.130.122:5147/GigaSolarBPM/SPfileUpload/:BPMBackFormId/:userid/:role
  // BPMBackFormId ⇒ BPMform單號
  // userid ⇒ 工號
  // role ⇒ 角色(編輯edit或查看view)
  // 開啟一個新網頁視窗 不要給user看到網址
  const roleValue = "view";

  const url = uploadURL(roleValue, filter);

  // 取得原始的 textarea 元素
  //   const originalElement = document.getElementById("ECContentDescAttTextArea");
  const originalElement = document.getElementById(changeHtmlId);
  if (originalElement) {
    // 獲取原始元素的樣式資訊
    const computedStyle = window.getComputedStyle(originalElement);
    const originalHeight = originalElement.offsetHeight || computedStyle.height;

    // 創建新的 iframe 元素
    const iframe = document.createElement("iframe");
    iframe.id = changeHtmlId; // 保持相同的 id
    iframe.src = url;
    iframe.style.width = "100%";

    // 保持原始高度，如果原始高度小於 800px 則使用 800px
    const minHeight = 800;
    const finalHeight = Math.max(
      parseInt(originalHeight) || minHeight,
      minHeight
    );
    iframe.style.height = finalHeight + "px";

    iframe.style.border = "1px solid #ccc";
    iframe.style.overflow = "auto"; // 確保有滾輪
    iframe.frameBorder = "0";
    iframe.scrolling = "yes"; // 明確啟用滾輪

    // 將原始元素替換為 iframe
    originalElement.parentNode.replaceChild(iframe, originalElement);

    // 使用 iframe-resizer.js 重新調整 iframe 大小
    iFrameResize(
      {
        log: true,
        autoResize: true,
        checkOrigin: false,
        resizeFrom: "parent",
        heightCalculationMethod: "max",
        onResized: function (messageData) {
          console.log("iframe resized:", messageData);
        },
        onInit: function (iframe) {
          console.log("iframe initialized:", iframe);
        },
      },
      `#${changeHtmlId}`
    ); // 指定要應用到的 iframe
  } else {
    console.error(`找不到 id 為 '${changeHtmlId}' 的元素`);
  }
}

function OpenReminderNoteImage() {
  if (activityId == "IssueECNReqUserTask") {
    FormUtil.showGridDialog("ReminderNoteImageDialog");
  }
}
// 等網頁載入完成後執行
window.onload = function () {
  OpenReminderNoteImage();
};
