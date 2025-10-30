import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';

// Pages
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import Airports from './pages/Airports';
import AirportDetail from './pages/AirportDetail';
import AirportMap from './pages/AirportMap';
import ItemTypesManagement from './pages/ItemTypesManagement';
import Settings from './pages/Settings';
import PAPIMeasurements from './pages/PAPIMeasurements';
import PAPIMeasurementsHistory from './pages/PAPIMeasurementsHistory';
import PAPIMeasurementsResults from './pages/PAPIMeasurementsResults';
import DroneMetadataTools from './pages/DroneMetadataTools';
import Layout from './components/Layout';

// Create Query Client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Routes component
const AppRoutes: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/" replace />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<PAPIMeasurementsHistory />} />
        <Route path="users" element={<Users />} />
        <Route path="airports" element={<Airports />} />
        <Route path="airports/:airportId" element={<AirportDetail />} />
        <Route path="airports/:airportId/map" element={<AirportMap />} />
        <Route path="item-types" element={<ItemTypesManagement />} />
        <Route path="papi-measurements" element={<PAPIMeasurements />} />
        <Route path="papi-measurements/history" element={<PAPIMeasurementsHistory />} />
        <Route path="papi-measurements/results/:sessionId" element={<PAPIMeasurementsResults />} />
        <Route path="tools/drone-metadata" element={<DroneMetadataTools />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<div className="p-6">Profile (TODO)</div>} />
      </Route>
      
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
