import React from 'react';
import { ChakraProvider } from '@chakra-ui/react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { Header, Sidebar, MainContent } from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute'; // Import ProtectedRoute
import { LoginPage, DataSourcesPage, MetadataPage } from './pages';
import { useAuth } from './contexts/AuthContext'; // To handle default redirection
import theme from './theme';
import './App.css';

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    // Optional: Show a global loading spinner while checking auth state initially
    // Or rely on ProtectedRoute's and LoginPage's individual loading states
    return null; // Or a global spinner component
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <div style={{ display: 'flex', flexGrow: 1 }}>
        <Sidebar />
        <MainContent>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            {/* Protected Routes */}
            <Route element={<ProtectedRoute />}>
              <Route path="/datasources" element={<DataSourcesPage />} />
              {/* Route for MetadataPage, :datasourceId is a URL parameter */}
              <Route path="/datasources/:datasourceId/metadata" element={<MetadataPage />} />
              {/* Remove old /metadata route if it's no longer used directly or was a placeholder */}
              {/* <Route path="/metadata" element={<MetadataPage />} /> */} {/* Assuming this was placeholder or general metadata */}
              {/* Add other protected routes here */}
            </Route>

            {/* Default route: Redirect to /datasources if authenticated, else to /login */}
            <Route
              path="/"
              element={
                isAuthenticated ? <Navigate to="/datasources" replace /> : <Navigate to="/login" replace />
              }
            />
            {/* You can also have a generic 404 page here */}
            {/* <Route path="*" element={<NotFoundPage />} /> */}
          </Routes>
        </MainContent>
      </div>
    </div>
  );
}

function App() {
  return (
    <ChakraProvider theme={theme}>
      <Router>
        {/* AuthProvider is in index.tsx, AppRoutes will use useAuth */}
        <AppRoutes />
      </Router>
    </ChakraProvider>
  );
}

export default App;
