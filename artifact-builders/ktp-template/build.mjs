import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = '/Users/intellectmac/Documents/Олимпиадники/intellect-platform';
const outputDir = path.join(root, 'outputs', 'ktp-import-2026');
const publicDir = path.join(root, 'artifacts', 'intellect-learning-platform', 'public', 'templates');
const outputPath = path.join(outputDir, 'КТП-шаблон-2026.xlsx');
const publicPath = path.join(publicDir, 'ktp-template-2026.xlsx');

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(publicDir, { recursive: true });

const workbook = Workbook.create();
const ktp = workbook.worksheets.add('КТП');
const guide = workbook.worksheets.add('Инструкция');
const font = 'Arial';
const primary = '#4F46E5';
const ink = '#172033';
const muted = '#64748B';
const border = '#D9E1EC';
const inputFill = '#FFF7D6';

ktp.showGridLines = false;
ktp.tabColor = primary;
ktp.getRange('A2:I2').merge();
ktp.getRange('A2').values = [['Календарно-тематический план']];
ktp.getRange('A2:I2').format = {
  font: { name: font, size: 16, bold: true, color: ink },
  verticalAlignment: 'center',
};
ktp.getRange('A2:I2').format.rowHeight = 30;
ktp.getRange('A3:I3').format.borders = { bottom: { style: 'thin', color: primary } };

ktp.getRange('A4:B8').values = [
  ['Предмет', 'Математика'],
  ['Класс', 7],
  ['Язык обучения', 'ru'],
  ['Часов в неделю', 4],
  ['Часов в год', null],
];
ktp.getRange('B8').formulas = [['=SUM(D11:D210)']];
ktp.getRange('A4:A8').format = { font: { name: font, size: 10, bold: true, color: ink } };
ktp.getRange('B4:B8').format = {
  fill: inputFill,
  font: { name: font, size: 10, color: ink },
  borders: { preset: 'outside', style: 'thin', color: border },
};
ktp.getRange('B5').dataValidation = { rule: { type: 'list', values: ['7', '8', '9', '10'] } };
ktp.getRange('B6').dataValidation = { rule: { type: 'list', values: ['ru', 'ky'] } };

const headers = ['Раздел', '№ урока', 'Тема урока', 'Часы', 'Тип урока', 'Цели обучения', 'Навыки', 'Ресурсы', 'Примечание'];
ktp.getRange('A10:I10').values = [headers];
ktp.getRange('A10:I10').format = {
  fill: primary,
  font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  borders: { preset: 'inside', style: 'thin', color: '#FFFFFF' },
};
ktp.getRange('A10:I10').format.rowHeight = 38;
ktp.getRange('A11:I40').format = {
  font: { name: font, size: 10, color: ink },
  verticalAlignment: 'top',
  wrapText: true,
  borders: { insideHorizontal: { style: 'thin', color: border }, bottom: { style: 'thin', color: border } },
};
ktp.getRange('A11:I40').format.rowHeight = 34;
ktp.getRange('A11:I210').format.fill = '#FFFFFF';
ktp.getRange('A11:D210').format.fill = inputFill;
ktp.getRange('F11:F210').format.fill = inputFill;
ktp.getRange('E11:E210').dataValidation = { rule: { type: 'list', values: ['Изучение', 'Контроль', 'Проект'] } };
ktp.getRange('D11:D210').dataValidation = { rule: { type: 'whole', operator: 'between', formula1: 1, formula2: 20 } };
ktp.freezePanes.freezeRows(10);
ktp.freezePanes.freezeColumns(2);

const widths = [22, 11, 31, 9, 16, 42, 30, 24, 24];
widths.forEach((width, index) => { ktp.getRangeByIndexes(0, index, 210, 1).format.columnWidth = width; });
ktp.getRange('B5:B8').format.numberFormat = '0';
ktp.getRange('A4:I40').format.verticalAlignment = 'center';
ktp.getRange('C11:I40').format.verticalAlignment = 'top';

guide.showGridLines = false;
guide.tabColor = '#94A3B8';
guide.getRange('A2:F2').merge();
guide.getRange('A2').values = [['Как заполнить КТП']];
guide.getRange('A2:F2').format = { font: { name: font, size: 16, bold: true, color: ink } };
guide.getRange('A3:F3').format.borders = { bottom: { style: 'thin', color: primary } };
guide.getRange('A5:B10').values = [
  ['1', 'Заполните предмет, класс, язык и нагрузку в жёлтых ячейках листа «КТП».'],
  ['2', 'Одна строка таблицы равна одной теме урока. Не объединяйте ячейки.'],
  ['3', 'Раздел можно указать только в первой теме раздела. В следующих строках ячейку можно оставить пустой.'],
  ['4', 'Цели обучения пишите как наблюдаемый результ: «объяснять», «сравнивать», «решать», «анализировать».'],
  ['5', 'Навыки можно разделять точкой с запятой. Для типа урока выберите «Изучение», «Контроль» или «Проект».'],
  ['6', 'Сохраните файл в формате XLSX и загрузите его на дашборде. Перед импортом темы можно исправить.'],
];
for (let row = 5; row <= 10; row += 1) guide.getRange(`B${row}:F${row}`).merge();
guide.getRange('A5:A10').format = { fill: primary, font: { name: font, size: 11, bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center', verticalAlignment: 'center' };
guide.getRange('B5:F10').format = { font: { name: font, size: 11, color: ink }, wrapText: true, verticalAlignment: 'center', borders: { bottom: { style: 'thin', color: border } } };
guide.getRange('A5:F10').format.rowHeight = 54;

guide.getRange('A13:I13').values = [headers];
guide.getRange('A13:I13').format = { fill: primary, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center', verticalAlignment: 'center', wrapText: true };
guide.getRange('A14:I15').values = [
  ['Числа и выражения', '1', 'Целые числа и координатная прямая', 2, 'Изучение', 'Сравнивать целые числа и объяснять их положение на координатной прямой.', 'сравнение; моделирование', 'Учебник, §1', ''],
  ['', '2', 'Действия с целыми числами', 1, 'Изучение', 'Решать задачи с целыми числами и проверять результат.', 'вычисление; самопроверка', 'Учебник, §2', ''],
];
guide.getRange('A14:I15').format = { font: { name: font, size: 9, color: ink }, wrapText: true, verticalAlignment: 'top', borders: { preset: 'all', style: 'thin', color: border } };
guide.getRange('A13:I15').format.rowHeight = 46;
widths.forEach((width, index) => { guide.getRangeByIndexes(0, index, 20, 1).format.columnWidth = width; });

workbook.recalculate();

const inspection = await workbook.inspect({ kind: 'table', range: 'КТП!A2:I15', include: 'values,formulas', tableMaxRows: 15, tableMaxCols: 9 });
await fs.writeFile(path.join(outputDir, 'inspection.ndjson'), inspection.ndjson, 'utf8');
const errors = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 100 }, summary: 'formula error scan' });
await fs.writeFile(path.join(outputDir, 'errors.ndjson'), errors.ndjson, 'utf8');

for (const [sheetName, range] of [['КТП', 'A2:I30'], ['Инструкция', 'A2:I15']]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: 'png' });
  await fs.writeFile(path.join(outputDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.copyFile(outputPath, publicPath);
console.log(JSON.stringify({ outputPath, publicPath }));
