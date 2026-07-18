import { Navigate, Outlet } from 'react-router-dom';
import { ROUTES } from '../constants/routes';

export const ProtectedRoute = () => {
  // Authentication is determined by the presence of the token
  const isAuthenticated = !!localStorage.getItem('access_token');

  return isAuthenticated ? <Outlet /> : <Navigate to={ROUTES.LOGIN} replace />;
};