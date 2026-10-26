import { useState } from 'react';
import './App.css';
import { useAuth } from './hooks/useAuth';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PatientRegistrationPage from './pages/PatientRegistrationPage';
import PatientsPage from './pages/PatientsPage';
import InterviewPage from './pages/InterviewPage';
import CaseReviewPage from './pages/CaseReviewPage';

// ── Navigation state ─────────────────────────────────────────────────────────
// page: 'dashboard' | 'register' | 'patients' | 'interview' | 'case-review'
// params: { encounterId, patientId, ... }

const NAV_ITEMS = [
  { page: 'dashboard',  icon: '⊞',  label: 'Dashboard' },
  { page: 'patients',   icon: '👥', label: 'Patients'  },
  { page: 'register',   icon: '+',  label: 'New Patient' },
];

export default function App() {
  const { user, isAuthenticated, login, logout } = useAuth();
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [pageParams, setPageParams] = useState({});

  function navigate(page, params = {}) {
    setCurrentPage(page);
    setPageParams(params);
  }

  // ── Not logged in ──────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return <LoginPage onLogin={login} />;
  }

  // ── Render current page ────────────────────────────────────────────────────
  function renderPage() {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardPage onNavigate={navigate} />;
      case 'patients':
        return <PatientsPage onNavigate={navigate} />;
      case 'register':
        return <PatientRegistrationPage onNavigate={navigate} />;
      case 'interview':
        return <InterviewPage encounterId={pageParams.encounterId} onNavigate={navigate} />;
      case 'case-review':
        return <CaseReviewPage encounterId={pageParams.encounterId} onNavigate={navigate} />;
      default:
        return <DashboardPage onNavigate={navigate} />;
    }
  }

  const pageTitle = {
    dashboard:    'Dashboard',
    patients:     'Patients',
    register:     'Register Patient',
    interview:    'Patient Interview',
    'case-review':'Case Review',
  }[currentPage] || 'PatientCase AI';

  const initials = (user.username || 'U').slice(0, 2).toUpperCase();

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">🏥</div>
          <div>
            <div className="logo-text">PatientCase AI</div>
            <div className="logo-sub">Clinical Handoff System</div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <div className="nav-section-title">Navigation</div>
          {NAV_ITEMS.map(item => (
            <button
              key={item.page}
              className={`nav-item ${currentPage === item.page ? 'active' : ''}`}
              onClick={() => navigate(item.page)}
              aria-current={currentPage === item.page ? 'page' : undefined}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}

          {/* Contextual nav items */}
          {currentPage === 'interview' && (
            <>
              <div className="nav-section-title">Current Session</div>
              <div className="nav-item active">
                <span className="nav-icon">▶</span>
                Interview #{pageParams.encounterId}
              </div>
            </>
          )}
          {currentPage === 'case-review' && (
            <>
              <div className="nav-section-title">Current Session</div>
              <div className="nav-item active">
                <span className="nav-icon">📋</span>
                Case #{pageParams.encounterId}
              </div>
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">{initials}</div>
            <div>
              <div className="user-name">{user.username}</div>
              <div className="user-role">{user.role}</div>
            </div>
          </div>
          <button
            className="btn btn-ghost btn-sm btn-full"
            onClick={logout}
            style={{ marginTop: 8 }}
            id="logout-btn"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="main-content">
        <header className="topbar">
          <div className="topbar-title">{pageTitle}</div>
          <div className="topbar-actions">
            <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>
              {user.role}
            </span>
          </div>
        </header>

        <main role="main">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
