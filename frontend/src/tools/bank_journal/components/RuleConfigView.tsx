import { Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  FIELD_LABEL,
  RULE_ACTION_FIELD_LABEL,
  RULE_OPERATOR_LABEL
} from '../constants';
import type { RuleAction, RuleCondition, RuleEditorData } from './RuleEditor';

/** 动作字段 label：优先业务动作字段字典，其次流水字段字典，最后原值。 */
function actionFieldLabel(key: string): string {
  return RULE_ACTION_FIELD_LABEL[key] ?? FIELD_LABEL[key] ?? key;
}

/** 条件字段 label：流水字段字典优先，最后原值。 */
function conditionFieldLabel(key: string): string {
  return FIELD_LABEL[key] ?? key;
}

interface RuleConfigViewProps {
  /** 规则配置数据（由 ruleDataFromBackend 从后端 JSON 解析得到）。 */
  data: RuleEditorData;
}

/**
 * 规则配置的只读结构化视图（详情页 / 版本历史复用）。
 *
 * 详情页默认状态应是「可读展示」，编辑是显式切换动作（Carbon Design System
 * read-only states 最佳实践）。本组件把规则的「条件」与「动作」明细以表格形式
 * 直接呈现，无需用户点开编辑 Modal 即可核对配置。
 */
export function RuleConfigView({ data }: RuleConfigViewProps) {
  const hasConditions = data.conditions.length > 0;
  const hasActions = data.actions.length > 0;

  if (!hasConditions && !hasActions) {
    return <Typography.Text type="secondary">该规则尚未配置条件与动作。</Typography.Text>;
  }

  return (
    <>
      {hasConditions && (
        <div style={{ marginBottom: 16 }}>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            触发条件（全部满足）
          </Typography.Title>
          <ConditionTable conditions={data.conditions} />
        </div>
      )}
      {hasActions && (
        <div>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            执行动作
          </Typography.Title>
          <ActionTable actions={data.actions} />
        </div>
      )}
    </>
  );
}

/** 条件明细表：字段（中文） | 操作符（中文） | 值。 */
function ConditionTable({ conditions }: { conditions: RuleCondition[] }) {
  const columns: ColumnsType<RuleCondition> = [
    {
      title: '流水字段',
      dataIndex: 'field',
      key: 'field',
      render: (_, c) => (
        <Tag color="blue">{conditionFieldLabel(c.field)}</Tag>
      )
    },
    {
      title: '判断方式',
      dataIndex: 'op',
      key: 'op',
      width: 120,
      render: (_, c) => RULE_OPERATOR_LABEL[c.op] ?? c.op
    },
    {
      title: '值',
      dataIndex: 'value',
      key: 'value',
      render: (_, c) => (
        <Typography.Text code>{c.value || '-'}</Typography.Text>
      )
    }
  ];
  return (
    <Table<RuleCondition>
      rowKey={(_, i) => String(i)}
      columns={columns}
      dataSource={conditions}
      pagination={false}
      size="small"
    />
  );
}

/** 动作明细表：设置字段（中文） = 值。 */
function ActionTable({ actions }: { actions: RuleAction[] }) {
  const columns: ColumnsType<RuleAction> = [
    {
      title: '设置字段',
      dataIndex: 'field',
      key: 'field',
      render: (_, a) => (
        <Tag color="geekblue">{actionFieldLabel(a.field)}</Tag>
      )
    },
    {
      title: '为',
      key: 'eq',
      width: 50,
      render: () => <Typography.Text type="secondary">=</Typography.Text>
    },
    {
      title: '取值',
      dataIndex: 'value',
      key: 'value',
      render: (_, a) => (
        <Typography.Text code>{a.value || '-'}</Typography.Text>
      )
    }
  ];
  return (
    <Table<RuleAction>
      rowKey={(_, i) => String(i)}
      columns={columns}
      dataSource={actions}
      pagination={false}
      size="small"
    />
  );
}
