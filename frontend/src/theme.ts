import type { ThemeConfig } from 'antd';
import { theme as antdTheme } from 'antd';

/**
 * FA Tools 设计系统 — 配色/字体取自集团 tokens.css（品牌红 + 品牌蓝 + 暖中性），
 * 圆角遵循 frontend-design skill（克制偏小、精致），不照搬 tokens 的 0 圆角。
 *
 * 统一在此维护，供 ConfigProvider（antd 全局）与 CSS 变量（自定义元素）共用。
 */

// ─── 品牌色（来自 tokens.css，集中导出供非 antd 场景引用）─────────────────
export const palette = {
  // 品牌红
  redPrimary: '#b5141d',
  redMid: '#cc4f58',
  redLight: '#f4ced0',
  redDark: '#8a1419',
  // 品牌蓝（结构色）
  bluePrimary: '#133f8e',
  blueMid: '#5574ac',
  bluePale: '#e8eff8',
  blueLight: '#b5c3db',
  blueDark: '#0d2e68',
  // 暖中性（带棕/暖偏移，非纯黑纯白）
  ink: '#1d1b1b',
  inkDark: '#24201f',
  muted: '#6f6864',
  rule: '#d8d0ca',
  fill: '#e9e7e6',
  paper: '#f5f2ee',
  white: '#ffffff'
} as const;

/** antd v5 主题：注入品牌色 + 字体 + 圆角。 */
export const themeConfig: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    // 主色：品牌红（主操作、链接、选中态）
    colorPrimary: palette.redPrimary,
    colorInfo: palette.bluePrimary,
    colorSuccess: '#2e7d32',
    colorWarning: '#b5141d',
    colorError: '#b5141d',

    // 中性（暖偏移）
    colorTextBase: palette.ink,
    colorBgBase: palette.white,
    colorBorder: palette.rule,
    colorBorderSecondary: palette.fill,
    colorBgLayout: palette.paper,
    colorBgContainer: palette.white,
    colorTextSecondary: palette.muted,

    // 圆角：遵循 frontend-design，克制偏小、精致
    borderRadius: 4,
    borderRadiusLG: 6,
    borderRadiusSM: 2,

    // 字体：楷体用于标题点睛（antd 标题级别靠 Typography 局部覆盖），
    // 正文/UI 用微软雅黑保证可读性，西文/数字 Lato
    fontFamily:
      "'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', Lato, sans-serif",
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeHeading1: 28,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 18,

    // 线条克制、阴影柔和（现代金融感）
    lineWidth: 1,
    controlHeight: 34,
    controlHeightLG: 40
  },
  components: {
    Layout: {
      siderBg: palette.inkDark,
      headerBg: palette.white,
      headerHeight: 56,
      bodyBg: palette.paper
    },
    Menu: {
      darkItemBg: palette.inkDark,
      darkSubMenuItemBg: palette.inkDark,
      darkItemSelectedBg: 'rgba(181, 20, 29, 0.18)',
      darkItemColor: 'rgba(245, 242, 238, 0.72)',
      darkItemHoverColor: palette.white,
      itemBorderRadius: 4,
      itemHeight: 40
    },
    Card: {
      borderRadiusLG: 6,
      headerBg: 'transparent',
      headerFontSize: 16
    },
    Table: {
      headerBg: palette.paper,
      headerColor: palette.muted,
      headerSplitColor: palette.rule,
      rowHoverBg: palette.bluePale,
      borderColor: palette.rule,
      cellPaddingBlock: 12
    },
    Button: {
      fontWeight: 500,
      primaryShadow: 'none',
      defaultShadow: 'none'
    },
    Tag: {
      borderRadiusSM: 2
    }
  }
};
