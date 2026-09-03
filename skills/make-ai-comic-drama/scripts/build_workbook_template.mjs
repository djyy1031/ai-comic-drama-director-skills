import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = process.argv[2];
if (!outputPath) {
  throw new Error("用法：node build_workbook_template.mjs <输出.xlsx>");
}

const workbook = Workbook.create();
const navy = "#0F172A";
const blue = "#1D4ED8";
const paleBlue = "#EFF6FF";
const paleGray = "#F8FAFC";
const white = "#FFFFFF";
const green = "#DCFCE7";
const amber = "#FEF3C7";
const red = "#FEE2E2";
const border = "#CBD5E1";

function colName(index) {
  let n = index + 1;
  let result = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result;
}

function styleDataSheet(sheet, title, headers, widths, tableName) {
  const lastCol = colName(headers.length - 1);
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${lastCol}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: white, size: 15 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${lastCol}1`).format.rowHeight = 30;
  sheet.getRange(`A2:${lastCol}2`).values = [headers];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: blue,
    font: { bold: true, color: white },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: border },
  };
  sheet.getRange(`A3:${lastCol}52`).format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: {
      insideHorizontal: { style: "thin", color: "#E2E8F0" },
      bottom: { style: "thin", color: border },
    },
  };
  sheet.getRange(`A3:${lastCol}3`).format.fill = paleBlue;
  headers.forEach((_, index) => {
    sheet.getRange(`${colName(index)}:${colName(index)}`).format.columnWidth = widths[index];
  });
  sheet.freezePanes.freezeRows(2);
  const table = sheet.tables.add(`A2:${lastCol}52`, true, tableName);
  table.style = "TableStyleMedium2";
  return { lastCol };
}

function addStatusFormatting(sheet, range) {
  const target = sheet.getRange(range);
  target.conditionalFormats.add("containsText", { text: "READY", format: { fill: green } });
  target.conditionalFormats.add("containsText", { text: "PASS", format: { fill: green } });
  target.conditionalFormats.add("containsText", { text: "PENDING", format: { fill: amber } });
  target.conditionalFormats.add("containsText", { text: "WARNING", format: { fill: amber } });
  target.conditionalFormats.add("containsText", { text: "FAIL", format: { fill: red } });
  target.conditionalFormats.add("containsText", { text: "BLOCKED", format: { fill: red } });
}

const overview = workbook.worksheets.add("项目总览");
const master = workbook.worksheets.add("母资产总表");
const cameras = workbook.worksheets.add("场景机位矩阵");
const matrix = workbook.worksheets.add("分镜组资产矩阵");
const subAssets = workbook.worksheets.add("子资产生产清单");
const video = workbook.worksheets.add("视频输入包");
const sound = workbook.worksheets.add("分集声音执行表");
overview.showGridLines = false;
overview.mergeCells("A1:F1");
overview.getRange("A1").values = [["AI漫剧生产信息表｜1.0.3"]];
overview.getRange("A1:F1").format = {
  fill: navy,
  font: { bold: true, color: white, size: 17 },
  verticalAlignment: "center",
};
overview.getRange("A1:F1").format.rowHeight = 34;
overview.getRange("A3:B8").values = [
  ["项目名", "填写项目名称"],
  ["模型配置", "seedance-2.0"],
  ["最终成片上限", 180],
  ["母资产数量", null],
  ["未完成必须资产", null],
  ["可生产视频任务", null],
];
overview.getRange("B6").formulas = [["=COUNTA('母资产总表'!B3:B52)"]];
overview.getRange("B7").formulas = [["=COUNTIFS('母资产总表'!G3:G52,3,'母资产总表'!H3:H52,\"<>READY\")"]];
overview.getRange("B8").formulas = [["=COUNTIF('视频输入包'!L3:L52,\"是\")"]];
overview.getRange("A3:A8").format = { fill: blue, font: { bold: true, color: white } };
overview.getRange("B3:B8").format = { fill: paleGray, borders: { preset: "outside", style: "thin", color: border } };
overview.getRange("B5").format.numberFormat = "0\" 秒\"";
overview.getRange("A10:F14").values = [
  ["使用规则", null, null, null, null, null],
  ["1", "只选择一个模型配置；2.0与2.5不能混用。", null, null, null, null],
  ["2", "每集最终成片不得超过180秒。", null, null, null, null],
  ["3", "三轮审核全部PASS后，视频任务才可生产。", null, null, null, null],
  ["4", "每个含对白、内心独白、旁白、画外音或系统语音的镜头，都必须在本镜全部描述最后追加：视频严禁出现台词、内心独白与系统语音字幕。", null, null, null, null],
];
overview.mergeCells("A10:F10");
for (let row = 11; row <= 14; row += 1) overview.mergeCells(`B${row}:F${row}`);
overview.getRange("A10:F10").format = { fill: navy, font: { bold: true, color: white } };
overview.getRange("A11:F14").format = { wrapText: true, fill: paleBlue };
overview.getRange("A:A").format.columnWidth = 18;
overview.getRange("B:F").format.columnWidth = 19;
overview.freezePanes.freezeRows(1);
overview.getRange("B4").dataValidation = { rule: { type: "list", values: ["seedance-2.0", "seedance-2.5"] } };

styleDataSheet(
  master,
  "母资产总表｜机器ID用于去重，视频提示词只使用原文标准名称",
  ["资产ID", "原文标准名称", "类型", "版本", "剧情功能", "复用范围", "必要性0-3", "状态", "来源", "授权状态", "提示词/备注"],
  [15, 22, 14, 12, 24, 15, 12, 14, 18, 16, 42],
  "MasterAssetTable",
);
master.getRange("A3:K3").values = [["CHAR-LZ", "林舟", "CHARACTER", "BASE", "主要角色", "GLOBAL", 3, "PENDING", "原创", "CONFIRMED", "示例行，可替换"]];
master.getRange("G3:G52").dataValidation = { rule: { type: "whole", operator: "between", formula1: 0, formula2: 3 } };
master.getRange("H3:H52").dataValidation = { rule: { type: "list", values: ["PENDING", "IN_PROGRESS", "READY", "BLOCKED", "STALE"] } };
addStatusFormatting(master, "H3:H52");

styleDataSheet(
  cameras,
  "场景机位矩阵｜12机位是参考覆盖模板，不强制全部生产",
  ["场景标准名称", "机位名称", "摄影机位置", "观察方向", "高度", "焦距/景别", "覆盖分镜组", "必要性0-3", "状态", "结构一致性说明"],
  [22, 18, 23, 23, 13, 18, 22, 12, 14, 38],
  "SceneCameraTable",
);
cameras.getRange("A3:J3").values = [["综合训练教室", "讲台向后排", "讲台中央前缘", "面向教室最后排", "胸口高度", "中景", "EP001-SG01", 3, "PENDING", "门窗、课桌、过道与母场景一致"]];
cameras.getRange("H3:H52").dataValidation = { rule: { type: "whole", operator: "between", formula1: 0, formula2: 3 } };
cameras.getRange("I3:I52").dataValidation = { rule: { type: "list", values: ["PENDING", "IN_PROGRESS", "READY", "BLOCKED", "STALE"] } };
addStatusFormatting(cameras, "I3:I52");

styleDataSheet(
  matrix,
  "分镜组资产矩阵｜逐集逐组确认实际调用资产",
  ["集数", "分镜组", "模型配置", "时长秒", "角色", "服装/状态", "场景", "机位", "道具", "UI/VFX", "子资产", "声音", "依赖状态"],
  [10, 15, 17, 11, 23, 22, 23, 20, 20, 20, 26, 24, 15],
  "ShotGroupAssetTable",
);
matrix.getRange("A3:M3").values = [[1, "EP001-SG01", "seedance-2.0", 15, "林舟、苏澄", "日常服/正常", "综合训练教室", "讲台向后排", "练习长剑", "无", "双人站位参考", "教室环境底噪", "PENDING"]];
matrix.getRange("C3:C52").dataValidation = { rule: { type: "list", values: ["seedance-2.0", "seedance-2.5"] } };
matrix.getRange("M3:M52").dataValidation = { rule: { type: "list", values: ["PENDING", "READY", "BLOCKED", "STALE"] } };
addStatusFormatting(matrix, "M3:M52");

styleDataSheet(
  subAssets,
  "子资产生产清单｜只生产确实提升视频稳定性的资产",
  ["子资产ID", "集数", "分镜组", "类型", "标准名称", "用途", "必要性0-3", "输入母资产", "状态", "提示词/制作要求"],
  [16, 10, 15, 20, 24, 28, 12, 28, 14, 45],
  "SubAssetTable",
);
subAssets.getRange("A3:J3").values = [["SUB-EP001-SG01-01", 1, "EP001-SG01", "BLOCKING", "林舟与苏澄双人站位", "锁定两人距离与朝向", 3, "林舟、苏澄、综合训练教室", "PENDING", "示例行，可替换"]];
subAssets.getRange("D3:D52").dataValidation = { rule: { type: "list", values: ["BLOCKING", "SEATING", "POSE", "CHARACTER_PROP", "EXPRESSION", "INTERACTION", "START_FRAME", "END_FRAME"] } };
subAssets.getRange("G3:G52").dataValidation = { rule: { type: "whole", operator: "between", formula1: 0, formula2: 3 } };
subAssets.getRange("I3:I52").dataValidation = { rule: { type: "list", values: ["PENDING", "IN_PROGRESS", "READY", "BLOCKED", "STALE"] } };
addStatusFormatting(subAssets, "I3:I52");

styleDataSheet(
  video,
  "视频输入包｜资产、制作说明与纯净提示词严格分层",
  ["集数", "分镜组", "模型配置", "实际时长秒", "时长例外原因", "内部镜头数", "资产调用清单", "制作说明与前后衔接", "纯净视频提示词", "三审状态", "时长检查", "可生产"],
  [10, 15, 17, 13, 24, 13, 38, 42, 55, 15, 14, 12],
  "VideoPackageTable",
);
video.getRange("A3:J3").values = [[1, "EP001-SG01", "seedance-2.0", 15, "", 5, "列出资产及锁定职责", "列出场景、光影、轴线、站位和声音衔接；默认不用首尾帧", "每个含语言镜头都在本镜末尾追加禁字幕固定句", "PENDING"]];
video.getRange("K3").formulas = [["=IF(B3=\"\",\"\",IF(C3=\"seedance-2.0\",IF(D3<=15,\"PASS\",\"FAIL\"),IF(C3=\"seedance-2.5\",IF(AND(D3<=30,OR(D3>=20,E3<>\"\")),\"PASS\",\"FAIL\"),\"FAIL\")))"]];
video.getRange("K3:K52").fillDown();
video.getRange("L3").formulas = [["=IF(B3=\"\",\"\",IF(AND(J3=\"PASS\",K3=\"PASS\"),\"是\",\"否\"))"]];
video.getRange("L3:L52").fillDown();
video.getRange("C3:C52").dataValidation = { rule: { type: "list", values: ["seedance-2.0", "seedance-2.5"] } };
video.getRange("J3:J52").dataValidation = { rule: { type: "list", values: ["PENDING", "PASS", "WARNING", "FAIL"] } };
addStatusFormatting(video, "J3:K52");

styleDataSheet(
  sound,
  "分集声音执行表｜粗剪后使用真实时间码",
  ["集数", "开始秒", "结束秒", "分镜组/镜头", "剧情事件", "情绪目标", "声音类别", "BGM类型", "节奏/能量", "环境声", "动作声", "转场/剧情音效", "进入/退出", "对白避让", "静默", "素材/状态", "来源/授权"],
  [10, 11, 11, 18, 25, 18, 18, 22, 18, 22, 22, 25, 22, 22, 12, 24, 22],
  "SoundCueTable",
);
sound.getRange("A3:Q3").values = [[1, 0, 15, "EP001-SG01", "教室对峙", "克制紧张", "AMBIENCE+BGM", "低频悬疑铺底", "缓慢/2", "教室远处人声与风扇", "脚步、衣料", "末尾短促提示音", "0秒淡入/15秒淡出", "对白期间降低音乐", "否", "PENDING", "待确认"]];
sound.getRange("G3:G52").dataValidation = { rule: { type: "list", values: ["DIALOGUE", "BGM", "AMBIENCE", "FOLEY", "ACTION", "TRANSITION", "STINGER", "SILENCE", "MIXED"] } };
sound.getRange("O3:O52").dataValidation = { rule: { type: "list", values: ["是", "否"] } };

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) used.format.font.name = "Microsoft YaHei";
}

const outputDir = path.dirname(outputPath);
await fs.mkdir(outputDir, { recursive: true });
const previewDir = path.join(outputDir, "previews");
await fs.mkdir(previewDir, { recursive: true });

for (const sheet of workbook.worksheets.items) {
  const preview = await workbook.render({
    sheetName: sheet.name,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const safeName = sheet.name.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(path.join(previewDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const inspection = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 8000,
  tableMaxRows: 4,
  tableMaxCols: 8,
  tableMaxCellChars: 80,
});
console.log(inspection.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(formulaErrors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`SAVED: ${outputPath}`);
