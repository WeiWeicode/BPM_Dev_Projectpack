// 把表格資料匯出成 CSV，方便貼進 Excel。加 BOM 讓 Excel 正確辨識 UTF-8。
export function downloadCsv(filename: string, headers: string[], rows: string[][]) {
  const escape = (cell: string) => `"${(cell ?? '').replace(/"/g, '""')}"`;
  const lines = [headers, ...rows].map((row) => row.map(escape).join(','));
  const blob = new Blob(['\uFEFF' + lines.join('\r\n')], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
