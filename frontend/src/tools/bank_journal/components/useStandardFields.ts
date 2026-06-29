import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../auth/useAuth';
import {
  getStandardSchema,
  standardFieldOptionsFromSchema,
  type StandardFieldOptionsState
} from '../api/customFields';
import { STANDARD_FIELDS } from '../constants';

/**
 * 拉取合并后的标准字段（内置 + 公司扩展），供编辑器下拉与类型映射使用。
 *
 * - 加载中/失败时回退到构建期内置字段（由 STANDARD_FIELDS 派生），不阻断页面
 * - 扩展字段增删后，调用 refetch() 刷新
 * - 未选择公司（currentCompanyId 为 null）时，跳过远程拉取，直接用内置字段兜底
 */
export function useStandardFields(): StandardFieldOptionsState & { refetch: () => void } {
  const { currentCompanyId } = useAuth();
  const [schema, setSchema] = useState<Awaited<ReturnType<typeof getStandardSchema>> | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = () => {
    if (!currentCompanyId) {
      setSchema(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    getStandardSchema(currentCompanyId)
      .then(setSchema)
      .catch(() => setSchema(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentCompanyId]);

  const derived = useMemo(() => {
    const runtime = standardFieldOptionsFromSchema(schema);
    // 回退：拉取失败或加载中时，用内置字段兜底，保证页面可用
    if (runtime.options.length === 0) {
      const options = STANDARD_FIELDS.map((f) => ({ value: f.key, label: f.label }));
      const typeMap: Record<string, string> = {};
      for (const f of STANDARD_FIELDS) typeMap[f.key] = f.type;
      return { options, typeMap };
    }
    return runtime;
  }, [schema]);

  return { ...derived, loading, refetch };
}
