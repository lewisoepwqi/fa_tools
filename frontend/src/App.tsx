import { Tabs } from 'antd';
import { useState } from 'react';
import { AppShell } from './components/AppShell';
import { AuditLogPage } from './pages/AuditLogPage';
import { BankTemplatePage } from './pages/BankTemplatePage';
import { ConversionRunListPage } from './pages/ConversionRunListPage';
import { JournalTemplatePage } from './pages/JournalTemplatePage';
import { MappingProfilePage } from './pages/MappingProfilePage';
import { RulePage } from './pages/RulePage';
import { UploadPage } from './pages/UploadPage';

function TemplatesView() {
  return (
    <Tabs
      defaultActiveKey="bank"
      items={[
        { key: 'bank', label: '银行流水模板', children: <BankTemplatePage /> },
        { key: 'journal', label: '日记账模板', children: <JournalTemplatePage /> },
        { key: 'mapping', label: '映射方案', children: <MappingProfilePage /> },
        { key: 'rule', label: '规则', children: <RulePage /> }
      ]}
    />
  );
}

export default function App() {
  const [page, setPage] = useState('upload');
  return (
    <AppShell activeKey={page} onNavigate={setPage}>
      {page === 'upload' && <UploadPage />}
      {page === 'runs' && <ConversionRunListPage />}
      {page === 'templates' && <TemplatesView />}
      {page === 'audit' && <AuditLogPage />}
    </AppShell>
  );
}
