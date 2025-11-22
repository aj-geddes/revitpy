import { z } from 'zod';

// Package Management Types
export const PackageVersionSchema = z.string().regex(/^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$/);

export const PackageDependencySchema = z.object({
  name: z.string(),
  version: z.string(),
  optional: z.boolean().default(false),
  dev: z.boolean().default(false),
});

export const PackageMetadataSchema = z.object({
  name: z.string(),
  version: PackageVersionSchema,
  description: z.string().optional(),
  author: z.string().optional(),
  maintainers: z.array(z.string()).default([]),
  license: z.string().optional(),
  homepage: z.string().url().optional(),
  repository: z.string().url().optional(),
  bugs: z.string().url().optional(),
  keywords: z.array(z.string()).default([]),
  category: z.string().optional(),
  tags: z.array(z.string()).default([]),
  revitVersions: z.array(z.string()).default([]),
  pythonVersion: z.string().optional(),
  dependencies: z.array(PackageDependencySchema).default([]),
  devDependencies: z.array(PackageDependencySchema).default([]),
  peerDependencies: z.array(PackageDependencySchema).default([]),
  files: z.array(z.string()).default([]),
  entry: z.string().optional(),
  scripts: z.record(z.string()).default({}),
  publishConfig: z.object({
    registry: z.string().url().optional(),
    access: z.enum(['public', 'restricted']).default('public'),
  }).optional(),
  revitPy: z.object({
    type: z.enum(['command', 'panel', 'tool', 'service', 'library']),
    permissions: z.array(z.string()).default([]),
    ui: z.object({
      framework: z.string().optional(),
      entry: z.string().optional(),
    }).optional(),
    install: z.object({
      preInstall: z.string().optional(),
      postInstall: z.string().optional(),
    }).optional(),
  }).optional(),
});

export type PackageVersion = z.infer<typeof PackageVersionSchema>;
export type PackageDependency = z.infer<typeof PackageDependencySchema>;
export type PackageMetadata = z.infer<typeof PackageMetadataSchema>;

export interface PackageInfo extends PackageMetadata {
  id: string;
  downloadCount: number;
  rating: {
    average: number;
    count: number;
    distribution: Record<string, number>;
  };
  publishDate: Date;
  lastUpdate: Date;
  size: number;
  verified: boolean;
  deprecated?: {
    reason: string;
    replacement?: string;
    date: Date;
  };
  versions: Array<{
    version: string;
    publishDate: Date;
    downloadCount: number;
    deprecated?: boolean;
  }>;
  readme?: string;
  changelog?: string;
  documentation?: string;
  screenshots?: string[];
  demo?: string;
}

export interface InstalledPackage extends PackageInfo {
  installDate: Date;
  installPath: string;
  status: 'active' | 'inactive' | 'error' | 'updating';
  autoUpdate: boolean;
  source: 'registry' | 'local' | 'git' | 'development';
  customConfig?: Record<string, unknown>;
}

export interface PackageRegistry {
  id: string;
  name: string;
  url: string;
  type: 'official' | 'community' | 'enterprise' | 'local';
  authenticated: boolean;
  trusted: boolean;
  enabled: boolean;
  priority: number;
  lastSync?: Date;
  packages: number;
  health: 'healthy' | 'degraded' | 'offline';
}

export interface PackageSearchResult {
  id: string;
  name: string;
  version: string;
  description?: string;
  author?: string;
  category?: string;
  tags: string[];
  rating: number;
  downloadCount: number;
  publishDate: Date;
  revitVersions: string[];
  verified: boolean;
  highlight?: {
    name?: string;
    description?: string;
    tags?: string[];
  };
}

export interface PackageSearchQuery {
  query?: string;
  category?: string;
  tags?: string[];
  revitVersions?: string[];
  author?: string;
  verified?: boolean;
  minRating?: number;
  sortBy?: 'relevance' | 'downloads' | 'rating' | 'updated' | 'created' | 'name';
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface PackageSearchResponse {
  results: PackageSearchResult[];
  total: number;
  facets: {
    categories: Array<{ name: string; count: number }>;
    tags: Array<{ name: string; count: number }>;
    authors: Array<{ name: string; count: number }>;
    revitVersions: Array<{ version: string; count: number }>;
  };
  suggestions?: string[];
}

export interface PackageInstallOptions {
  version?: string;
  registry?: string;
  force?: boolean;
  skipDependencies?: boolean;
  allowPrerelease?: boolean;
  installPath?: string;
  autoUpdate?: boolean;
  customConfig?: Record<string, unknown>;
}

export interface PackageInstallResult {
  success: boolean;
  package?: InstalledPackage;
  dependencies?: InstalledPackage[];
  errors?: Array<{
    package: string;
    message: string;
    code: string;
  }>;
  warnings?: Array<{
    package: string;
    message: string;
  }>;
  log: Array<{
    timestamp: Date;
    level: 'info' | 'warn' | 'error';
    message: string;
    package?: string;
  }>;
}

export interface PackageUpdateInfo {
  package: string;
  currentVersion: string;
  availableVersion: string;
  type: 'major' | 'minor' | 'patch';
  changelog?: string;
  breaking?: boolean;
  security?: boolean;
  size: number;
  dependencies: Array<{
    name: string;
    currentVersion: string;
    newVersion: string;
  }>;
}

export interface PackagePublication {
  package: PackageMetadata;
  files: Array<{
    path: string;
    content: Buffer | string;
  }>;
  registry: string;
  token?: string;
  dryRun?: boolean;
}

export interface PackageValidationResult {
  valid: boolean;
  errors: Array<{
    field: string;
    message: string;
    code: string;
  }>;
  warnings: Array<{
    field: string;
    message: string;
    code: string;
  }>;
  suggestions?: Array<{
    field: string;
    message: string;
    fix?: unknown;
  }>;
}

export interface PackageStats {
  downloads: {
    total: number;
    lastWeek: number;
    lastMonth: number;
    trend: 'up' | 'down' | 'stable';
    history: Array<{
      date: Date;
      count: number;
    }>;
  };
  versions: {
    total: number;
    latest: string;
    beta: string | null;
    deprecated: string[];
  };
  ratings: {
    average: number;
    count: number;
    distribution: Record<string, number>;
    recent: Array<{
      rating: number;
      comment?: string;
      date: Date;
      user: string;
    }>;
  };
  dependencies: {
    dependents: number;
    dependencies: number;
    outdated: number;
    vulnerable: number;
  };
}
