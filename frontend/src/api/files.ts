import { apiClient } from './client';

export async function uploadBankStatement(file: File, companyId: string) {
  const form = new FormData();
  // company_id 由调用方传入（来自公司切换器）；uploaded_by 由后端从 JWT 推导，前端不再自报身份
  form.append('company_id', companyId);
  form.append('file', file);
  const response = await apiClient.post('/api/files/upload', form);
  return response.data;
}
