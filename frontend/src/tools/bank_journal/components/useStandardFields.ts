import { useEffect, useMemo, useState } from 'react';
import {
  getStandardSchema,
  standardFieldOptionsFromSchema,
  type StandardFieldOptionsState
} from '../api/customFields';
import { STANDARD_FIELDS } from '../constants';

const COMPANY_ID = 'company-1';

/**
 * 拉取合并后的标准字段（内置 + 公司扩展），供编辑器下拉与类型映射使用。
 *
 * - 加载中/失败时回退到构建期内置字段（由 STANDARD_FIELDS 派生），不阻断页面
 * - 扩展字段增删后，调用 refetch() 刷新
 */
export function useStandardFields(): StandardFieldOptionsState & { refetch: () => void } {
  const [schema, setSchema] = useState<Awaited<ReturnType<typeof getStandardSchema>> | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = () => {
    setLoading(true);
    getStandardSchema(COMPANY_ID)
      .then(setSchema)
      .catch(() => setSchema(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
