import { expect, test } from '@playwright/test';

test('shows bank statement journal workspace', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('银行流水转日记账')).toBeVisible();
  await expect(page.getByText('流水上传').first()).toBeVisible();
});
