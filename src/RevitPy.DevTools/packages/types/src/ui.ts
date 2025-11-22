import { z } from 'zod';

// UI Component Types
export interface RevitPyPanel {
  id: string;
  title: string;
  type: 'dockable' | 'modal' | 'modeless';
  position: 'left' | 'right' | 'bottom' | 'floating';
  size: {
    width: number;
    height: number;
    minWidth?: number;
    minHeight?: number;
    maxWidth?: number;
    maxHeight?: number;
  };
  resizable: boolean;
  closable: boolean;
  visible: boolean;
  url: string;
  permissions: string[];
}

export interface RevitPyCommand {
  id: string;
  name: string;
  displayName: string;
  description?: string;
  tooltip?: string;
  icon?: string;
  category: string;
  ribbon: {
    tab: string;
    panel: string;
    position: number;
  };
  shortcut?: string;
  enabled: boolean;
  visible: boolean;
  handler: string;
}

export interface RevitPyTool {
  id: string;
  name: string;
  displayName: string;
  description?: string;
  icon?: string;
  cursor?: string;
  mode: 'one_shot' | 'continuous' | 'preview';
  instructions?: string[];
  contextualHelp?: string;
  handler: string;
}

// Theme Types
export const ThemeSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  type: z.enum(['light', 'dark']),
  colors: z.object({
    primary: z.string(),
    secondary: z.string(),
    accent: z.string(),
    background: z.string(),
    surface: z.string(),
    text: z.string(),
    textSecondary: z.string(),
    border: z.string(),
    success: z.string(),
    warning: z.string(),
    error: z.string(),
    info: z.string(),
  }),
  fonts: z.object({
    primary: z.string(),
    mono: z.string(),
    sizes: z.object({
      xs: z.string(),
      sm: z.string(),
      base: z.string(),
      lg: z.string(),
      xl: z.string(),
      '2xl': z.string(),
      '3xl': z.string(),
      '4xl': z.string(),
    }),
  }),
  spacing: z.object({
    xs: z.string(),
    sm: z.string(),
    md: z.string(),
    lg: z.string(),
    xl: z.string(),
    '2xl': z.string(),
    '3xl': z.string(),
    '4xl': z.string(),
  }),
  borderRadius: z.object({
    none: z.string(),
    sm: z.string(),
    base: z.string(),
    md: z.string(),
    lg: z.string(),
    xl: z.string(),
    full: z.string(),
  }),
  shadows: z.object({
    sm: z.string(),
    base: z.string(),
    md: z.string(),
    lg: z.string(),
    xl: z.string(),
  }),
});

export type Theme = z.infer<typeof ThemeSchema>;

// UI State Types
export interface UIState {
  theme: 'light' | 'dark' | 'auto';
  language: string;
  panels: Record<string, RevitPyPanel>;
  activePanel?: string;
  sidebarCollapsed: boolean;
  notifications: Notification[];
  modal?: {
    type: string;
    props: Record<string, unknown>;
  };
}

export interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message?: string;
  duration?: number;
  actions?: Array<{
    label: string;
    action: () => void;
    style?: 'primary' | 'secondary';
  }>;
  timestamp: Date;
  persistent?: boolean;
}

// Form Types
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'multiselect' | 'date' | 'file' | 'password';
  required?: boolean;
  placeholder?: string;
  description?: string;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
    custom?: (value: unknown) => boolean | string;
  };
  options?: Array<{
    value: unknown;
    label: string;
    disabled?: boolean;
  }>;
  defaultValue?: unknown;
  disabled?: boolean;
  hidden?: boolean;
}

export interface FormSchema {
  fields: FormField[];
  layout: 'vertical' | 'horizontal' | 'grid';
  columns?: number;
  sections?: Array<{
    title: string;
    description?: string;
    fields: string[];
    collapsible?: boolean;
    collapsed?: boolean;
  }>;
}

// Data Visualization Types
export interface ChartData {
  labels: string[];
  datasets: Array<{
    label: string;
    data: number[];
    backgroundColor?: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
    fill?: boolean;
    tension?: number;
  }>;
}

export interface ChartOptions {
  responsive: boolean;
  maintainAspectRatio: boolean;
  plugins: {
    legend: {
      display: boolean;
      position: 'top' | 'bottom' | 'left' | 'right';
    };
    title: {
      display: boolean;
      text?: string;
    };
    tooltip: {
      enabled: boolean;
      mode: 'index' | 'dataset' | 'point' | 'nearest' | 'x' | 'y';
    };
  };
  scales?: {
    x?: {
      type: 'linear' | 'logarithmic' | 'category' | 'time';
      display: boolean;
      title: {
        display: boolean;
        text?: string;
      };
    };
    y?: {
      type: 'linear' | 'logarithmic' | 'category' | 'time';
      display: boolean;
      title: {
        display: boolean;
        text?: string;
      };
    };
  };
}

// Layout Types
export interface LayoutConfig {
  type: 'grid' | 'flex' | 'absolute';
  areas?: string[][];
  columns?: string;
  rows?: string;
  gap?: string;
  padding?: string;
  margin?: string;
  responsive?: {
    breakpoint: string;
    config: Partial<LayoutConfig>;
  }[];
}

// Accessibility Types
export interface A11yConfig {
  announcements: boolean;
  keyboardNavigation: boolean;
  highContrast: boolean;
  reducedMotion: boolean;
  screenReader: boolean;
  fontSize: 'small' | 'normal' | 'large' | 'x-large';
  colorBlindness: 'none' | 'protanopia' | 'deuteranopia' | 'tritanopia';
}
