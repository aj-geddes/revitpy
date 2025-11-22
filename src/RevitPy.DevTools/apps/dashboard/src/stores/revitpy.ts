import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  ConnectionStatus,
  RuntimeStatus,
  RevitPyRuntime,
  RevitPyEnvironment,
  PerformanceMetrics,
  ProjectInfo,
  InstalledPackage,
} from '@revitpy/types';

interface RevitPyState {
  // Connection & Runtime
  connectionStatus: ConnectionStatus;
  runtimeStatus: RuntimeStatus;
  runtime: RevitPyRuntime | null;

  // Environment
  environments: RevitPyEnvironment[];
  activeEnvironment: string | null;

  // Performance
  performanceMetrics: PerformanceMetrics | null;

  // Projects
  projects: ProjectInfo[];
  activeProject: string | null;

  // Packages
  installedPackages: InstalledPackage[];

  // UI State
  sidebarCollapsed: boolean;

  // Actions
  setConnectionStatus: (status: ConnectionStatus) => void;
  setRuntimeStatus: (status: RuntimeStatus) => void;
  setRuntime: (runtime: RevitPyRuntime | null) => void;
  setEnvironments: (environments: RevitPyEnvironment[]) => void;
  setActiveEnvironment: (id: string | null) => void;
  setPerformanceMetrics: (metrics: PerformanceMetrics) => void;
  setProjects: (projects: ProjectInfo[]) => void;
  setActiveProject: (id: string | null) => void;
  addProject: (project: ProjectInfo) => void;
  updateProject: (id: string, updates: Partial<ProjectInfo>) => void;
  removeProject: (id: string) => void;
  setInstalledPackages: (packages: InstalledPackage[]) => void;
  addPackage: (pkg: InstalledPackage) => void;
  updatePackage: (id: string, updates: Partial<InstalledPackage>) => void;
  removePackage: (id: string) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useRevitPyStore = create<RevitPyState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    connectionStatus: 'disconnected',
    runtimeStatus: 'stopped',
    runtime: null,
    environments: [],
    activeEnvironment: null,
    performanceMetrics: null,
    projects: [],
    activeProject: null,
    installedPackages: [],
    sidebarCollapsed: false,

    // Actions
    setConnectionStatus: (status) => set({ connectionStatus: status }),
    setRuntimeStatus: (status) => set({ runtimeStatus: status }),
    setRuntime: (runtime) => set({ runtime }),

    setEnvironments: (environments) => set({ environments }),
    setActiveEnvironment: (id) => set({ activeEnvironment: id }),

    setPerformanceMetrics: (metrics) => set({ performanceMetrics: metrics }),

    setProjects: (projects) => set({ projects }),
    setActiveProject: (id) => set({ activeProject: id }),
    addProject: (project) => set((state) => ({
      projects: [...state.projects, project]
    })),
    updateProject: (id, updates) => set((state) => ({
      projects: state.projects.map(p => p.id === id ? { ...p, ...updates } : p)
    })),
    removeProject: (id) => set((state) => ({
      projects: state.projects.filter(p => p.id !== id),
      activeProject: state.activeProject === id ? null : state.activeProject
    })),

    setInstalledPackages: (packages) => set({ installedPackages: packages }),
    addPackage: (pkg) => set((state) => ({
      installedPackages: [...state.installedPackages, pkg]
    })),
    updatePackage: (id, updates) => set((state) => ({
      installedPackages: state.installedPackages.map(p =>
        p.id === id ? { ...p, ...updates } : p
      )
    })),
    removePackage: (id) => set((state) => ({
      installedPackages: state.installedPackages.filter(p => p.id !== id)
    })),

    setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  }))
);

// Selectors
export const useConnectionStatus = () => useRevitPyStore(state => state.connectionStatus);
export const useRuntimeStatus = () => useRevitPyStore(state => state.runtimeStatus);
export const useRuntime = () => useRevitPyStore(state => state.runtime);
export const useEnvironments = () => useRevitPyStore(state => state.environments);
export const useActiveEnvironment = () => {
  const environments = useEnvironments();
  const activeEnvironmentId = useRevitPyStore(state => state.activeEnvironment);
  return environments.find(env => env.name === activeEnvironmentId) || null;
};
export const useProjects = () => useRevitPyStore(state => state.projects);
export const useActiveProject = () => {
  const projects = useProjects();
  const activeProjectId = useRevitPyStore(state => state.activeProject);
  return projects.find(p => p.id === activeProjectId) || null;
};
export const useInstalledPackages = () => useRevitPyStore(state => state.installedPackages);
export const usePerformanceMetrics = () => useRevitPyStore(state => state.performanceMetrics);
