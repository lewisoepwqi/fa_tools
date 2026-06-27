import { InboxOutlined } from '@ant-design/icons';
import { Button, Card, Space, Typography, Upload, message } from 'antd';
import type { UploadFile } from 'antd';
import { useState } from 'react';
import { createConversionRun } from '../api/conversionRuns';
import { uploadBankStatement } from '../api/files';
import { ConversionRunDetailPage } from './ConversionRunDetailPage';
import type { ConversionRunResponse } from '../types/conversion';

export function UploadPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [run, setRun] = useState<ConversionRunResponse | null>(null);

  const handleStart = async () => {
    const files = fileList
      .map((file) => file.originFileObj as File | undefined)
      .filter((file): file is File => file != null);
    if (files.length === 0) {
      return;
    }
    setLoading(true);
    try {
      const sourceFileIds: string[] = [];
      for (const file of files) {
        const uploaded = await uploadBankStatement(file);
        sourceFileIds.push(uploaded.id as string);
      }
      const result = (await createConversionRun(sourceFileIds)) as ConversionRunResponse;
      setRun(result);
      message.success('转换完成');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="work-card">
        <Typography.Title level={3}>流水上传</Typography.Title>
        <Typography.Paragraph type="secondary">
          上传银行流水 CSV / XLSX 文件，生成公司日记账预览。
        </Typography.Paragraph>
        <Upload.Dragger
          multiple
          accept=".csv,.xlsx"
          fileList={fileList}
          beforeUpload={() => false}
          onChange={({ fileList: nextFileList }) => setFileList(nextFileList)}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">支持 .csv / .xlsx，可多选</p>
        </Upload.Dragger>
        <Button
          type="primary"
          loading={loading}
          disabled={fileList.length === 0}
          onClick={handleStart}
          style={{ marginTop: 16 }}
        >
          开始转换
        </Button>
      </Card>
      {run && <ConversionRunDetailPage run={run} />}
    </Space>
  );
}
