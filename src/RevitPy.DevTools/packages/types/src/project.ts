// Project Management Types
export interface ProjectScaffoldOptions {
  name: string;
  template: string;
  path: string;
  author?: string;
  description?: string;
  license?: string;
  revitVersions?: string[];
  pythonVersion?: string;
  uiFramework?: 'react' | 'vue' | 'svelte' | 'vanilla';
  features?: string[];
  gitInit?: boolean;
  installDependencies?: boolean;
  variables?: Record<string, unknown>;
}

export interface ProjectScaffoldResult {
  success: boolean;
  project?: ProjectInfo;
  files?: Array<{
    path: string;
    type: 'created' | 'modified' | 'skipped';
    size: number;
  }>;
  log: Array<{
    timestamp: Date;
    level: 'info' | 'warn' | 'error';
    message: string;
  }>;
  errors?: string[];
  warnings?: string[];
}

export interface ProjectValidation {
  valid: boolean;
  issues: Array<{
    type: 'error' | 'warning' | 'info';
    category: 'structure' | 'dependencies' | 'configuration' | 'code' | 'security';
    message: string;
    file?: string;
    line?: number;
    column?: number;
    fix?: {
      description: string;
      automatic: boolean;
      action: () => void;
    };
  }>;
  score: number;
  suggestions: string[];
}

export interface ProjectBuildOptions {
  target: 'development' | 'production';
  outputPath?: string;
  minify?: boolean;
  sourceMaps?: boolean;
  typeCheck?: boolean;
  lint?: boolean;
  test?: boolean;
  clean?: boolean;
  watch?: boolean;
}

export interface ProjectBuildResult {
  success: boolean;
  outputPath: string;
  files: Array<{
    path: string;
    size: number;
    type: 'entry' | 'chunk' | 'asset';
  }>;
  assets: Array<{
    name: string;
    size: number;
    type: string;
  }>;
  warnings?: string[];
  errors?: string[];
  stats: {
    buildTime: number;
    totalSize: number;
    chunks: number;
    modules: number;
  };
}

export interface ProjectDeployOptions {
  target: 'local' | 'team' | 'organization' | 'public';
  registry?: string;
  version?: string;
  tag?: string;
  dryRun?: boolean;
  skipTests?: boolean;
  skipLint?: boolean;
  notes?: string;
}

export interface ProjectDeployResult {
  success: boolean;
  version: string;
  url?: string;
  deploymentId: string;
  files: Array<{
    path: string;
    uploaded: boolean;
    size: number;
  }>;
  log: Array<{
    timestamp: Date;
    level: 'info' | 'warn' | 'error';
    message: string;
  }>;
}

export interface ProjectDependency {
  name: string;
  version: string;
  type: 'dependency' | 'devDependency' | 'peerDependency';
  source: 'npm' | 'pypi' | 'revitpy' | 'local';
  installed: boolean;
  outdated: boolean;
  vulnerable: boolean;
  size?: number;
  license?: string;
  description?: string;
}

export interface ProjectEnvironment {
  name: string;
  active: boolean;
  pythonVersion: string;
  path: string;
  packages: ProjectDependency[];
  variables: Record<string, string>;
  created: Date;
  lastUsed: Date;
  size: number;
}

export interface ProjectSettings {
  general: {
    name: string;
    version: string;
    description?: string;
    author?: string;
    license?: string;
  };
  build: {
    entry: string;
    outputDir: string;
    publicDir?: string;
    minify: boolean;
    sourceMaps: boolean;
    target: string[];
  };
  development: {
    port: number;
    host: string;
    hotReload: boolean;
    autoSave: boolean;
    liveReload: boolean;
    proxy?: Record<string, string>;
  };
  testing: {
    framework: 'pytest' | 'unittest' | 'jest';
    coverage: boolean;
    watch: boolean;
    parallel: boolean;
    timeout: number;
  };
  linting: {
    enabled: boolean;
    rules: Record<string, unknown>;
    ignorePatterns: string[];
    fixOnSave: boolean;
  };
  formatting: {
    enabled: boolean;
    rules: Record<string, unknown>;
    formatOnSave: boolean;
  };
  typeChecking: {
    enabled: boolean;
    strict: boolean;
    checkJs: boolean;
    incremental: boolean;
  };
  deployment: {
    defaultTarget: string;
    registry?: string;
    skipTests: boolean;
    skipLint: boolean;
    preDeployScript?: string;
    postDeployScript?: string;
  };
}

export interface ProjectActivity {
  id: string;
  type: 'build' | 'test' | 'deploy' | 'install' | 'update' | 'debug' | 'run';
  status: 'running' | 'success' | 'failed' | 'cancelled';
  startTime: Date;
  endTime?: Date;
  duration?: number;
  user?: string;
  details?: Record<string, unknown>;
  log?: Array<{
    timestamp: Date;
    level: string;
    message: string;
  }>;
}

export interface ProjectMetrics {
  files: {
    total: number;
    python: number;
    ui: number;
    tests: number;
    docs: number;
  };
  lines: {
    total: number;
    code: number;
    comments: number;
    blank: number;
  };
  size: {
    total: number;
    source: number;
    dependencies: number;
    build: number;
  };
  complexity: {
    cyclomatic: number;
    cognitive: number;
    maintainability: number;
  };
  quality: {
    coverage: number;
    bugs: number;
    vulnerabilities: number;
    codeSmells: number;
    techDebt: number;
  };
  performance: {
    buildTime: number;
    testTime: number;
    bundleSize: number;
    loadTime: number;
  };
}

export interface ProjectCollaboration {
  repository?: {
    url: string;
    provider: 'github' | 'gitlab' | 'bitbucket' | 'azure';
    branch: string;
    lastCommit: {
      hash: string;
      message: string;
      author: string;
      date: Date;
    };
    status: {
      ahead: number;
      behind: number;
      dirty: boolean;
      staged: number;
      unstaged: number;
      untracked: number;
    };
  };
  team?: Array<{
    id: string;
    name: string;
    email: string;
    role: 'owner' | 'maintainer' | 'developer' | 'viewer';
    active: boolean;
    lastSeen: Date;
  }>;
  issues?: Array<{
    id: string;
    title: string;
    status: 'open' | 'closed';
    assignee?: string;
    labels: string[];
    created: Date;
    updated: Date;
  }>;
  pullRequests?: Array<{
    id: string;
    title: string;
    status: 'open' | 'merged' | 'closed';
    author: string;
    reviewer?: string;
    created: Date;
    updated: Date;
  }>;
}
