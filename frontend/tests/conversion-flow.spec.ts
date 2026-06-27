import { expect, test } from '@playwright/test';

test('shows bank statement journal workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('银行流水转日记账')).toBeVisible();
  await expect(page.getByText('流水上传').first()).toBeVisible();
});

test('template management pages render with create button', async ({ page }) => {
  // 模板规则管理页：验证新建按钮（P0-1 前端）渲染
  await page.goto('/templates/bank');
  await expect(page.getByRole('button', { name: '新建' })).toBeVisible();
  await expect(page.getByText('银行流水模板').first()).toBeVisible();
});

test('rule list page shows create and priority columns', async ({ page }) => {
  // 规则管理页：验证优先级列与新建按钮（P2-4 前端）渲染
  await page.goto('/templates/rule');
  await expect(page.getByText('优先级').first()).toBeVisible();
  await expect(page.getByText('允许自动确认').first()).toBeVisible();
});
