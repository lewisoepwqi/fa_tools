import { InboxOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Form,
  Input,
  Space,
  Spin,
  Steps,
  Upload
} from 'antd';
import type { UploadProps } from 'antd';
import type { RcFile } from 'antd/es/upload';
import { useEffect, useState } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { uploadBankStatement } from '../../../api/files';
import { message } from '../../../components/antdApp';
import { FILE_TYPE_LABEL } from '../constants';
import { detectJournalTemplate, type JournalDetectResult } from '../api/journalTemplates';
import {
  JournalColumnsEditor,
  columnsFromBackend,
  type JournalColumn
} from './JournalColumnsEditor';

const { Dragger } = Upload;

export interface JournalTemplateWizardValues {
  name: string;
  /** detect 识别结果（来自后端），用户核对后随模板一起保存。 */
  detect: JournalDetectResult;
  /** 列编辑结果（用户在识别基础上增删改/勾选必填）。 */
  columns: JournalColumn[];
  sample_file_id?: string;
}

interface JournalTemplateWizardProps {
  /** 提交（保存模板）。父组件负责调 API。 */
  onSubmit: (values: JournalTemplateWizardValues) => Promise<void>;
  onCancel: () => void;
  /** 提交按钮 loading。 */
  submitting?: boolean;
  /** 预填值（编辑场景：从已有版本回填，不重新上传）。 */
  initialValues?: Partial<JournalTemplateWizardValues>;
  /** 是否跳过上传步骤（编辑已有版本时）。 */
  skipUpload?: boolean;
}

/**
 * 日记账模板配置向导（对齐银行模板的 BankTemplateWizard 体验）。
 *
 * 新建流程：填写名称 → 上传样本自动识别列 → 确认保存。
 * 识别后用 JournalColumnsEditor 展示列名，用户可增删改/勾选必填。
 */
export function JournalTemplateWizard({
  onSubmit,
  onCancel,
  submitting,
  initialValues,
  skipUpload
}: JournalTemplateWizardProps) {
  const { currentCompanyId } = useAuth();
  const firstStep = skipUpload ? 1 : 0;
  const [current, setCurrent] = useState(firstStep);
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const [detect, setDetect] = useState<JournalDetectResult | null>(
    initialValues?.detect ?? null
  );
  const [columns, setColumns] = useState<JournalColumn[]>(
    initialValues?.columns ?? columnsFromBackend(null, null)
  );
  const [sampleFileId, setSampleFileId] = useState<string | undefined>(
    initialValues?.sample_file_id
  );
  // name 提升为组件级 state，脱离 Form 生命周期（同 BankTemplateWizard）。
  const [name, setName] = useState(initialValues?.name ?? '');

  // 编辑场景：父组件回填可能在挂载后才到，同步一次。
  useEffect(() => {
    if (skipUpload && initialValues?.detect) {
      setDetect(initialValues.detect);
    }
    if (initialValues?.columns) {
      setColumns(initialValues.columns);
    }
    if (initialValues?.sample_file_id) {
      setSampleFileId(initialValues.sample_file_id);
    }
    if (initialValues?.name !== undefined) {
      setName(initialValues.name);
    }
  }, [skipUpload, initialValues?.detect, initialValues?.columns, initialValues?.sample_file_id, initialValues?.name]);

  const handleNextFromBasic = async () => {
    try {
      await form.validateFields();
    } catch {
      return;
    }
    setCurrent(1);
  };

  const handleUploadAndDetect = async (file: RcFile) => {
    if (!currentCompanyId) {
      message.error('请先在右上角选择公司');
      return false;
    }
    setUploading(true);
    try {
      const uploaded = await uploadBankStatement(file, currentCompanyId);
      const result = await detectJournalTemplate(uploaded.id);
      setDetect(result);
      // 把识别出的列名灌入编辑器（required_columns 决定勾选状态）
      setColumns(columnsFromBackend(result.columns, result.required_columns));
      setSampleFileId(uploaded.id);
      message.success('已自动识别列名，请核对');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '识别失败，请检查文件');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const uploadProps: UploadProps = {
    accept: '.csv,.xlsx,.xls',
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      void handleUploadAndDetect(file as RcFile);
      return false;
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      message.error('请输入模板名称');
      return;
    }
    // detect 可为 null（用户选择不上传，纯手填列）——此时用默认 file_type
    const fileType = detect?.file_type ?? 'xlsx';
    await onSubmit({
      name: name.trim(),
      detect: detect ?? {
        file_type: fileType,
        sheet_name: '',
        header_row_index: 0,
        data_start_row_index: 1,
        columns: columns.map((c) => c.name).filter(Boolean),
        required_columns: columns.filter((c) => c.required).map((c) => c.name)
      },
      columns,
      sample_file_id: sampleFileId
    });
  };

  const steps = skipUpload
    ? [{ title: '基本信息' }, { title: '确认保存' }]
    : [{ title: '基本信息' }, { title: '上传样本识别' }, { title: '确认保存' }];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Steps current={current} size="small" items={steps} />

      {/* 步骤 1：基本信息 */}
      {current === 0 && (
        <Form
          form={form}
          layout="vertical"
          initialValues={{ name }}
        >
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input
              placeholder="如：标准日记账"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Form.Item>
          <div style={{ textAlign: 'right' }}>
            <Button onClick={onCancel} style={{ marginRight: 8 }}>
              取消
            </Button>
            <Button type="primary" onClick={handleNextFromBasic}>
              下一步
            </Button>
          </div>
        </Form>
      )}

      {/* 步骤 2：上传样本 + 自动识别 */}
      {current === 1 && !skipUpload && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Dragger {...uploadProps} disabled={uploading}>
            {uploading ? (
              <Spin tip="正在识别...">
                <div style={{ padding: 16 }} />
              </Spin>
            ) : (
              <>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽上传一份日记账样本</p>
                <p className="ant-upload-hint">支持 .xlsx / .csv，系统将自动识别列名</p>
              </>
            )}
          </Dragger>

          {detect && (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                message={`已识别：${FILE_TYPE_LABEL[detect.file_type] ?? detect.file_type}，表头在第 ${detect.header_row_index + 1} 行`}
              />
              <JournalColumnsEditor value={columns} onChange={setColumns} />
            </Space>
          )}

          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => setCurrent(0)} style={{ marginRight: 8 }}>
              上一步
            </Button>
            <Button type="primary" disabled={!detect} onClick={() => setCurrent(2)}>
              下一步
            </Button>
          </div>
        </Space>
      )}

      {/* 编辑场景的步骤 1（跳过上传）直接展示预填列 */}
      {current === 1 && skipUpload && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <JournalColumnsEditor value={columns} onChange={setColumns} />
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => setCurrent(0)} style={{ marginRight: 8 }}>
              上一步
            </Button>
            <Button type="primary" loading={submitting} onClick={handleSave}>
              保存
            </Button>
          </div>
        </Space>
      )}

      {/* 步骤 3：确认保存 */}
      {current === 2 && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Alert
            type="success"
            showIcon
            message="请核对列配置，确认无误后保存"
            description="如识别有误，可返回上一步重新上传样本或手动调整。"
          />
          <JournalColumnsEditor value={columns} onChange={setColumns} />
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => setCurrent(skipUpload ? 0 : 1)} style={{ marginRight: 8 }}>
              上一步
            </Button>
            <Button type="primary" loading={submitting} onClick={handleSave}>
              保存模板
            </Button>
          </div>
        </Space>
      )}
    </Space>
  );
}
