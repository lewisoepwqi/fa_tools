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
import { message } from '../../../components/antdApp';
import { uploadBankStatement } from '../../../api/files';
import { detectBankTemplate } from '../api/bankTemplates';
import { DetectResultView } from './DetectResultView';
import { useStandardFields } from './useStandardFields';

const COMPANY_ID = 'company-1';

const { Dragger } = Upload;

export interface BankTemplateWizardValues {
  name: string;
  bank_name?: string;
  /** detect 识别结果（来自后端），用户核对后随模板一起保存。 */
  detect: {
    file_type: string;
    sheet_name: string;
    header_row_index: number;
    data_start_row_index: number;
    field_aliases: Record<string, string>;
    amount_mode: string;
    amount_config: Record<string, string>;
    date_formats: string[];
  };
  sample_file_id?: string;
}

interface BankTemplateWizardProps {
  /** 提交（保存模板）。父组件负责调 API。 */
  onSubmit: (values: BankTemplateWizardValues) => Promise<void>;
  onCancel: () => void;
  /** 提交按钮 loading。 */
  submitting?: boolean;
  /** 预填值（编辑场景：从已有版本回填基本信息，detect 可选）。 */
  initialValues?: Partial<BankTemplateWizardValues>;
  /** 是否跳过上传步骤（编辑已有版本时：用预填的 detect，不重新上传）。 */
  skipUpload?: boolean;
}

/**
 * 银行流水模板配置向导。
 *
 * 新建流程：填写基本信息 → 上传样本自动识别 → 确认保存。
 * 核心体验：调用后端 detect 自动识别表头/字段/金额模式，财务只需核对，
 * 无需手填技术字段（行索引、英文枚举）。
 */
export function BankTemplateWizard({
  onSubmit,
  onCancel,
  submitting,
  initialValues,
  skipUpload
}: BankTemplateWizardProps) {
  // 步骤：编辑场景跳过上传（步骤 1）
  const firstStep = skipUpload ? 1 : 0;
  const standardFields = useStandardFields();
  const [current, setCurrent] = useState(firstStep);
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const [detect, setDetect] = useState<BankTemplateWizardValues['detect'] | null>(
    initialValues?.detect ?? null
  );
  const [sampleFileId, setSampleFileId] = useState<string | undefined>(
    initialValues?.sample_file_id
  );
  // name/bank_name 提升为组件级 state，脱离 Form 生命周期。
  // 原因：步骤 0 的 <Form> 在切换到后续步骤时被卸载，form.getFieldsValue() 可能拿不到
  // 已填的 name；编辑流程下 Form 更是从未挂载。改为受控 state 后，handleSave 在任意
  // 步骤都能稳定读到值，避免 payload 缺 name → 后端 422。
  const [name, setName] = useState(initialValues?.name ?? '');
  const [bankName, setBankName] = useState(initialValues?.bank_name ?? '');

  // 编辑场景（skipUpload）：父组件回填的 initialValues 可能在本组件挂载后才到
  // （详情数据异步加载）。useState 只取初值，故这里同步一次。
  useEffect(() => {
    if (skipUpload && initialValues?.detect) {
      setDetect(initialValues.detect);
    }
    if (initialValues?.sample_file_id) {
      setSampleFileId(initialValues.sample_file_id);
    }
    if (initialValues?.name !== undefined) {
      setName(initialValues.name);
    }
    if (initialValues?.bank_name !== undefined) {
      setBankName(initialValues.bank_name);
    }
  }, [skipUpload, initialValues?.detect, initialValues?.sample_file_id, initialValues?.name, initialValues?.bank_name]);

  const handleNextFromBasic = async () => {
    // 仍用 Form 做必填校验（保留 rules 体验），但值已同步到 state，不依赖 Form 持久化。
    try {
      await form.validateFields();
    } catch {
      return;
    }
    setCurrent(1);
  };

  // 字段别名就地纠正：detect 是启发式自动识别会认错列名，这里回写到 detect state。
  // 保存时 handleSave 把 detect 整体提交，无需改保存链路。
  const handleAliasesChange = (next: Record<string, string>) => {
    setDetect((prev) => (prev ? { ...prev, field_aliases: next } : prev));
  };

  const handleUploadAndDetect = async (file: RcFile) => {
    setUploading(true);
    try {
      const uploaded = await uploadBankStatement(file);
      const result = await detectBankTemplate(uploaded.id, COMPANY_ID);
      setDetect(result);
      setSampleFileId(uploaded.id);
      message.success('已自动识别流水格式，请核对');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '识别失败，请检查文件');
    } finally {
      setUploading(false);
    }
    // 阻止 Upload 自身的上传行为
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
    // name/bank_name 由组件级 state 持有（不依赖 Form），任意步骤都能稳定读取。
    if (!name.trim()) {
      message.error('请输入模板名称');
      return;
    }
    // 类型守卫：detect 必须是完整对象才能提交，否则 amount_mode 等必填字段缺失
    // 会导致后端 422（amount_mode 是 BankTemplateVersionCreate 必填项）。
    if (
      !detect ||
      !detect.file_type ||
      !detect.amount_mode ||
      typeof detect.header_row_index !== 'number' ||
      typeof detect.data_start_row_index !== 'number'
    ) {
      message.error('识别结果不完整，请重新上传样本完成识别');
      return;
    }
    await onSubmit({
      name: name.trim(),
      bank_name: bankName.trim() || undefined,
      detect,
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
          initialValues={{
            name: name,
            bank_name: bankName
          }}
        >
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input
              placeholder="如：中国银行企业网银流水"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Form.Item>
          <Form.Item name="bank_name" label="银行名称">
            <Input
              placeholder="如：中国银行"
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
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
                <p className="ant-upload-text">点击或拖拽上传一份该银行的流水样本</p>
                <p className="ant-upload-hint">支持 .xlsx / .xls / .csv，系统将自动识别格式</p>
              </>
            )}
          </Dragger>

          {detect && <DetectResultView
            config={detect}
            onFieldAliasesChange={handleAliasesChange}
            standardFieldOptions={standardFields.options}
          />}

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

      {/* 编辑场景的步骤 1（跳过上传）直接展示预填 detect */}
      {current === 1 && skipUpload && detect && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <DetectResultView
            config={detect}
            onFieldAliasesChange={handleAliasesChange}
            standardFieldOptions={standardFields.options}
          />
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
      {current === 2 && detect && (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Alert
            type="success"
            showIcon
            message="请核对识别结果，确认无误后保存"
            description="如识别有误，可返回上一步重新上传样本或手动调整。"
          />
          <DetectResultView
            config={detect}
            onFieldAliasesChange={handleAliasesChange}
            standardFieldOptions={standardFields.options}
          />
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
