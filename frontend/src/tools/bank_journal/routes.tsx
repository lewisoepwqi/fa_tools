import { Tabs } from 'antd';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { BankTemplateDetailPage } from './pages/BankTemplateDetailPage';
import { BankTemplatePage } from './pages/BankTemplatePage';
import { ConversionRunDetailPage } from './pages/ConversionRunDetailPage';
import { ConversionRunListPage } from './pages/ConversionRunListPage';
import { CustomFieldPage } from './pages/CustomFieldPage';
import { JournalTemplateDetailPage } from './pages/JournalTemplateDetailPage';
import { JournalTemplatePage } from './pages/JournalTemplatePage';
import { MappingProfileDetailPage } from './pages/MappingProfileDetailPage';
import { MappingProfilePage } from './pages/MappingProfilePage';
import { RuleDetailPage } from './pages/RuleDetailPage';
import { RulePage } from './pages/RulePage';
import { UploadPage } from './pages/UploadPage';

/**
 * 模板规则的 4-Tab 布局。Tab 的选中与切换由 URL 驱动（每个列表有独立可分享 URL），
 * 各列表内部点击行再跳转到对应详情路由。
 */
function TemplatesLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  // 当前激活 tab = 路径分段，如 /bank-journal/templates/rule/123 → rule
  const segment = location.pathname.split('/')[3] ?? 'bank';
  return (
    <Tabs
      activeKey={segment}
      onChange={(key) => navigate(`/bank-journal/templates/${key}`)}
      items={[
        { key: 'bank', label: '银行流水模板', children: <BankTemplatePage /> },
        { key: 'journal', label: '日记账模板', children: <JournalTemplatePage /> },
        { key: 'mapping', label: '映射方案', children: <MappingProfilePage /> },
        { key: 'rule', label: '规则', children: <RulePage /> },
        { key: 'field', label: '标准字段', children: <CustomFieldPage /> }
      ]}
    />
  );
}

/**
 * 银行流水转日记账工具的全部路由（挂在 /bank-journal 命名空间下）。
 * 由 registry 注入到根 App。
 */
export function BankJournalRoutes() {
  return (
      <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/runs" element={<ConversionRunListPage />} />
      <Route path="/runs/:runId" element={<ConversionRunDetailPage />} />
      <Route path="/templates" element={<Navigate to="/bank-journal/templates/bank" replace />} />
      <Route path="/templates/bank" element={<TemplatesLayout />} />
      <Route path="/templates/bank/:id" element={<BankTemplateDetailPage />} />
      <Route path="/templates/journal" element={<TemplatesLayout />} />
      <Route path="/templates/journal/:id" element={<JournalTemplateDetailPage />} />
      <Route path="/templates/mapping" element={<TemplatesLayout />} />
      <Route path="/templates/mapping/:id" element={<MappingProfileDetailPage />} />
      <Route path="/templates/rule" element={<TemplatesLayout />} />
      <Route path="/templates/rule/:id" element={<RuleDetailPage />} />
      <Route path="/templates/field" element={<TemplatesLayout />} />
    </Routes>
  );
}
