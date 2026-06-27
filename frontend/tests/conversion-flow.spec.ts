import { expect, test } from '@playwright/test';

test('shows bank statement journal workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('流水转日记账')).toBeVisible();
  await expect(page.getByText('流水上传').first()).toBeVisible();
});

test('template management pages render with create button', async ({ page }) => {
  // 模板规则管理页：验证新建按钮（P0-1 前端）渲染
  await page.goto('/bank-journal/templates/bank');
  await expect(page.getByRole('button', { name: '新建' })).toBeVisible();
  await expect(page.getByText('银行流水模板').first()).toBeVisible();
});

test('rule list page shows create and priority columns', async ({ page }) => {
  // 规则管理页：验证优先级列与新建按钮（P2-4 前端）渲染
  await page.goto('/bank-journal/templates/rule');
  await expect(page.getByText('优先级').first()).toBeVisible();
  await expect(page.getByText('允许自动确认').first()).toBeVisible();
});

test('tool sidebar submenu exposes all sections and navigates', async ({ page }) => {
  // 侧边栏子菜单：流水上传 / 处理批次 / 模板规则 都应可见且可点击到达
  await page.goto('/bank-journal');
  // 三个子菜单项可见
  await expect(page.getByRole('menuitem', { name: '流水上传' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '处理批次' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '模板规则' })).toBeVisible();

  // 点击「处理批次」进入批次列表页
  await page.getByRole('menuitem', { name: '处理批次' }).click();
  await expect(page).toHaveURL(/\/bank-journal\/runs$/);

  // 点击「模板规则」进入模板页（默认银行流水模板 tab）
  await page.getByRole('menuitem', { name: '模板规则' }).click();
  await expect(page).toHaveURL(/\/bank-journal\/templates\/bank$/);
});

test('rule editor uses visual builder instead of JSON textarea', async ({ page }) => {
  // 规则新建：应是可视化条件构造器，不再有 JSON 文本框
  await page.goto('/bank-journal/templates/rule');
  await page.getByRole('button', { name: '新建' }).click();
  // 自然语言回显标题可见（证明走了可视化编辑器）
  await expect(page.getByText('规则含义').first()).toBeVisible();
  // 条件区与动作区标题可见
  await expect(page.getByText('满足以下【全部】条件').first()).toBeVisible();
  await expect(page.getByText('则 设置以下字段').first()).toBeVisible();
  // 不应再有 JSON 文本框的提示文案
  await expect(page.getByText(/条件（JSON）/)).toHaveCount(0);
  await expect(page.getByText(/动作（JSON）/)).toHaveCount(0);
});

test('journal template editor shows column management instead of JSON', async ({ page }) => {
  // 日记账模板新建：应是列编辑器，可见默认列
  await page.goto('/bank-journal/templates/journal');
  await page.getByRole('button', { name: '新建' }).click();
  await expect(page.getByText('输出列配置').first()).toBeVisible();
  // 列编辑器独有的"添加列"按钮可见
  await expect(page.getByRole('button', { name: '添加列' })).toBeVisible();
  // 默认 4 列的汇总文案可见
  await expect(page.getByText(/共 4 列，其中必填 3 列/)).toBeVisible();
  // 不应再有 JSON 数组提示
  await expect(page.getByText(/列定义（JSON 数组）/)).toHaveCount(0);
});

