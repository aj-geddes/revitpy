import { Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { Layout } from '@/components/layout';
import { PageLoader } from '@/components/page-loader';
import { ErrorBoundary } from '@/components/error-boundary';

// Lazy load pages for better performance
const Dashboard = lazy(() => import('@/pages/dashboard'));
const Projects = lazy(() => import('@/pages/projects'));
const ProjectDetails = lazy(() => import('@/pages/projects/[id]'));
const Packages = lazy(() => import('@/pages/packages'));
const PackageDetails = lazy(() => import('@/pages/packages/[id]'));
const REPL = lazy(() => import('@/pages/repl'));
const Monitoring = lazy(() => import('@/pages/monitoring'));
const Settings = lazy(() => import('@/pages/settings'));
const Help = lazy(() => import('@/pages/help'));

function LazyPage({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        
        <Route 
          path="/dashboard" 
          element={
            <LazyPage>
              <Dashboard />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/projects" 
          element={
            <LazyPage>
              <Projects />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/projects/:id" 
          element={
            <LazyPage>
              <ProjectDetails />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/packages" 
          element={
            <LazyPage>
              <Packages />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/packages/:id" 
          element={
            <LazyPage>
              <PackageDetails />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/repl" 
          element={
            <LazyPage>
              <REPL />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/monitoring" 
          element={
            <LazyPage>
              <Monitoring />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/settings" 
          element={
            <LazyPage>
              <Settings />
            </LazyPage>
          } 
        />
        
        <Route 
          path="/help" 
          element={
            <LazyPage>
              <Help />
            </LazyPage>
          } 
        />
        
        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}