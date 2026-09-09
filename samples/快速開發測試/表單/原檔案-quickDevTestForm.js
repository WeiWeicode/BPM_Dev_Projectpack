function formCreate(){
  return true;
}
function formOpen(){
  return true;
}
function formSave(){
  return true;
}
function formClose(){
  return true;
}
function formDispatch(){
  return true;
}function Grid10_add_onclick(){
  if(true){
    Grid10Obj.addRow();
    Grid10Obj.clearBinding();
    return true;
  }else{
    return false;
  }
}
function Grid10_edit_onclick(){
  if(true){
    Grid10Obj.editRow();
    Grid10Obj.clearBinding();
    return true;
  }else{
    return false;
  }
}
function Grid10_delete_onclick(){
  if(true){
    console.log("Grid10_delete_onclick");
    Grid10Obj.deleteRow();
    Grid10Obj.clearBinding();
    return true;
  }else{
    return false;
  }
}
