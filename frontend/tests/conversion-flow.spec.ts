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
