import { z } from 'zod';

// Revit API Types
export interface RevitElement {
  id: string;
  name: string;
  category: string;
  type: string;
  parameters: Record<string, unknown>;
  geometry?: unknown;
  level?: string;
  workset?: string;
}

export interface RevitDocument {
  id: string;
  name: string;
  path?: string;
  isActive: boolean;
  isModified: boolean;
  version: string;
  elements: number;
  families: number;
  views: number;
  sheets: number;
}

export interface RevitTransaction {
  id: string;
  name: string;
  status: 'pending' | 'started' | 'committed' | 'rollback' | 'failed';
  startTime: Date;
  endTime?: Date;
  changes: Array<{
    elementId: string;
    action: 'create' | 'modify' | 'delete';
    before?: unknown;
    after?: unknown;
  }>;
}

// API Operation Types
export const RevitApiOperationSchema = z.object({
  method: z.string(),
  parameters: z.record(z.unknown()).optional(),
  elementId: z.string().optional(),
  documentId: z.string().optional(),
  transactionName: z.string().optional(),
});

export type RevitApiOperation = z.infer<typeof RevitApiOperationSchema>;

export interface RevitApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: string;
  };
  executionTime: number;
  transactionId?: string;
}

// Query Types
export interface ElementQuery {
  category?: string[];
  type?: string[];
  level?: string[];
  workset?: string[];
  parameters?: Record<string, unknown>;
  geometry?: {
    intersects?: unknown;
    contains?: unknown;
    within?: unknown;
  };
  limit?: number;
  offset?: number;
  orderBy?: string;
  orderDirection?: 'asc' | 'desc';
}

export interface QueryResult<T = RevitElement> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
  executionTime: number;
}

// Geometry Types
export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface BoundingBox {
  min: Point3D;
  max: Point3D;
}

export interface Transform {
  translation: Vector3D;
  rotation: {
    axis: Vector3D;
    angle: number;
  };
  scale: Vector3D;
}

// Parameter Types
export interface RevitParameter {
  name: string;
  displayName: string;
  type: 'string' | 'number' | 'boolean' | 'date' | 'guid' | 'reference';
  value: unknown;
  isReadOnly: boolean;
  isShared: boolean;
  group: string;
  unit?: string;
}

export interface ParameterDefinition {
  name: string;
  displayName: string;
  type: string;
  category: string[];
  shared: boolean;
  instance: boolean;
  reporting: boolean;
  formula?: string;
  tooltip?: string;
}

// Family Types
export interface FamilyInfo {
  name: string;
  category: string;
  path?: string;
  isLoaded: boolean;
  symbols: FamilySymbol[];
  parameters: ParameterDefinition[];
}

export interface FamilySymbol {
  name: string;
  id: string;
  parameters: Record<string, unknown>;
  isActive: boolean;
}

// View Types
export interface ViewInfo {
  id: string;
  name: string;
  type: 'floor_plan' | 'ceiling_plan' | 'elevation' | 'section' | '3d' | 'schedule' | 'sheet';
  level?: string;
  scale: number;
  template?: string;
  isTemplate: boolean;
}

// Material Types
export interface MaterialInfo {
  id: string;
  name: string;
  category: string;
  properties: {
    thermal?: Record<string, number>;
    structural?: Record<string, number>;
    appearance?: Record<string, unknown>;
  };
  assets: {
    appearance?: string;
    thermal?: string;
    structural?: string;
  };
}