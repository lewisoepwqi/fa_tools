import { apiClient } from './client';

export async function uploadBankStatement(file: File) {
  const form = new FormData();
  form.append('company_id', 'company-1');
  form.append('uploaded_by', 'user-1');
  form.append('file', file);
  const response = await apiClient.post('/api/files/upload', form);
  return response.data;
}
