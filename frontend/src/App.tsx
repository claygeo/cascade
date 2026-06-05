import { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import RunView from "./pages/RunView";
import WorkflowEditor from "./pages/WorkflowEditor";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="center" style={{ height: "60vh" }}>
        <span className="spinner" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/app"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/app/workflows/new"
        element={
          <RequireAuth>
            <WorkflowEditor />
          </RequireAuth>
        }
      />
      <Route
        path="/app/workflows/:id"
        element={
          <RequireAuth>
            <WorkflowEditor />
          </RequireAuth>
        }
      />
      <Route
        path="/app/runs/:id"
        element={
          <RequireAuth>
            <RunView />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
