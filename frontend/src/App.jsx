import { useState, useEffect, useCallback } from "react";
import { StoreProvider } from "./state/store";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Register from "./pages/Register";
import PatientList from "./pages/PatientList";
import Interview from "./pages/Interview";
import Documents from "./pages/Documents";
import DoctorReview from "./pages/DoctorReview";
import AuditLog from "./pages/AuditLog";
import PatientPortal from "./pages/PatientPortal";
import apiClient from "./api/client";

const PAGES = {
  dashboard: Dashboard,
  portal: PatientPortal,
  patients: PatientList,
  register: Register,
  interview: Interview,
  documents: Documents,
  review: DoctorReview,
  audit: AuditLog,
};

const ROLE_PAGES = {
  doctor: ["dashboard", "patients", "register", "interview", "documents", "review"],
  staff: ["dashboard", "patients", "register", "interview", "documents"],
  patient: ["portal", "interview", "documents"],
  admin: ["dashboard", "patients", "register", "interview", "documents", "review", "audit"],
};

export default function App() {
  const [user, setUser] = useState(() => {
    const token = apiClient.getToken();
    return token ? apiClient.getUser() : null;
  });

  const [sessionMessage, setSessionMessage] = useState(null);

  const getInitialPage = (userObj) => {
    if (!userObj) return "dashboard";
    const role = (userObj.role || "doctor").toLowerCase();
    return role === "patient" ? "portal" : "dashboard";
  };

  const [page, setPage] = useState(() => getInitialPage(user));

  // Listen to session expiry events from apiClient
  useEffect(() => {
    apiClient.setOnUnauthorized((msg) => {
      setUser(null);
      setSessionMessage(msg || "Your session has expired. Please log in again.");
      setPage("dashboard");
    });
  }, []);

  const handleLogin = (authenticatedUser) => {
    setUser(authenticatedUser);
    setSessionMessage(null);
    const startPage = getInitialPage(authenticatedUser);
    setPage(startPage);
  };

  const handleLogout = async () => {
    await apiClient.logout();
    setUser(null);
    setPage("dashboard");
  };

  const go = useCallback((targetPage) => {
    const userRole = (user?.role || "doctor").toLowerCase();
    const allowed = ROLE_PAGES[userRole] || ["dashboard"];

    if (!allowed.includes(targetPage)) {
      // Role violation guard: redirect to allowed page
      const fallback = allowed[0] || "dashboard";
      setPage(fallback);
      return;
    }

    setPage(targetPage);
    window.scrollTo(0, 0);
  }, [user]);

  // If page is not allowed for the logged in user, redirect to first allowed page
  useEffect(() => {
    if (user) {
      const userRole = (user.role || "doctor").toLowerCase();
      const allowed = ROLE_PAGES[userRole] || ["dashboard"];
      if (!allowed.includes(page)) {
        setPage(allowed[0]);
      }
    }
  }, [user, page]);

  const Page = PAGES[page] || Dashboard;

  return (
    <StoreProvider>
      {user ? (
        <Shell user={user} page={page} go={go} onLogout={handleLogout}>
          <Page go={go} user={user} />
        </Shell>
      ) : (
        <Login onLogin={handleLogin} sessionMessage={sessionMessage} />
      )}
    </StoreProvider>
  );
}
