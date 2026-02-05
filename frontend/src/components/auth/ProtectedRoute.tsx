import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

interface ProtectedRouteProps {
    requiredPermission?: string;
    requiredRole?: 'founder' | 'daena_vp' | 'agent' | 'viewer';
}

export function ProtectedRoute({ requiredPermission, requiredRole }: ProtectedRouteProps) {
    const { isAuthenticated, user, checkPermission } = useAuthStore();

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    if (requiredRole && user?.role !== requiredRole && user?.role !== 'founder') {
        return <Navigate to="/" replace />;
    }

    if (requiredPermission && !checkPermission(requiredPermission)) {
        return <Navigate to="/" replace />;
    }

    return <Outlet />;
}
