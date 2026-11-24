import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { AdminHome, AdminLayout } from "./AdminLayout";
import { ForcedPasswordChange } from "./ChangePassword";
import { Guard } from "./Guard";
import { LoginPage } from "./login/LoginPage";
import { AgentsPage } from "./pages/AgentsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { AlertsPage } from "./pages/AlertsPage";
import { DistancePage } from "./pages/DistancePage";
import { AuditPage } from "./pages/AuditPage";
import { GeneralPage } from "./pages/GeneralPage";
import { OrgPage } from "./pages/OrgPage";
import { ConfigPage } from "./pages/ConfigPage";
import { ReportsPage } from "./pages/ReportsPage";
import { EmployeeDetailPage } from "./pages/EmployeeDetailPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { JournalPage } from "./pages/JournalPage";
import { UsersPage } from "./pages/UsersPage";
import { ZonesPage } from "./pages/ZonesPage";

function Routed() {
  const { user } = useAuth();
  if (!user) return <LoginPage />;
  if (user.must_change_password) return <ForcedPasswordChange />;
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<AdminHome />} />
        <Route path="dashboard" element={<Guard right="logs.view"><DashboardPage /></Guard>} />
        <Route path="employes" element={<Guard right="employees.view"><EmployeesPage /></Guard>} />
        <Route path="employes/:id" element={<Guard right="employees.view"><EmployeeDetailPage /></Guard>} />
        <Route path="organisation" element={<Guard right="employees.view"><OrgPage /></Guard>} />
        <Route path="zones" element={<Guard right="zones.view"><ZonesPage /></Guard>} />
        <Route path="distance-conforme" element={<Guard right="reports.view"><DistancePage /></Guard>} />
        <Route path="telephones" element={<Guard right="zones.view"><DevicesPage /></Guard>} />
        <Route path="agents" element={<Guard right="zones.view"><AgentsPage /></Guard>} />
        <Route path="journal" element={<Guard right="logs.view"><JournalPage /></Guard>} />
        <Route path="audit" element={<Guard right="audit.view"><AuditPage /></Guard>} />
        <Route path="rapports" element={<Guard right="reports.view"><ReportsPage /></Guard>} />
        <Route path="alertes" element={<Guard right="reports.view"><AlertsPage /></Guard>} />
        <Route path="general" element={<GeneralPage />} />
        <Route path="configuration" element={<Guard right="system.config"><ConfigPage /></Guard>} />
        <Route path="utilisateurs" element={<Guard right="users.manage"><UsersPage /></Guard>} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Route>
    </Routes>
  );
}

/** Everything under /admin: the only part of the app that asks for a login. */
export function AdminApp() {
  return (
    <AuthProvider>
      <Routed />
    </AuthProvider>
  );
}
