/**
 * Main Layout Component
 * Includes sidebar navigation and main content area
 */

import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Layout.css';

// Helper function to get page title based on route
const getPageTitle = (pathname) => {
  const titleMap = {
    '/dashboard': 'Dashboard',
    '/recorders': 'My Recorders',
    '/recorders/create': 'Create Strategy',
    '/recorders/edit': 'Edit Strategy',
    '/trader/accounts': 'Account Management',
    '/trader/strategies': 'My Traders',
    '/trader/control-center': 'Control Center',
    '/settings': 'Settings',
  };

  for (const [path, title] of Object.entries(titleMap)) {
    if (pathname === path || pathname.startsWith(path + '/')) {
      return title;
    }
  }
  return 'Dashboard';
};

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  // Update time every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const toggleDarkMode = () => {
    // Dark mode toggle functionality (can be enhanced later)
    document.body.classList.toggle('dark-mode');
  };

  const toggleDropdown = () => {
    setDropdownOpen(!dropdownOpen);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownOpen && !event.target.closest('.dropdown')) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [dropdownOpen]);

  return (
    <div className="wrapper">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? '' : 'sidebar-mini'}`} data-color="blue">
        <div className="sidebar-wrapper">
          <div className="logo">
            <Link to="/" className="simple-text logo-mini">
              <div className="logo-img">
                <img src="/client_specifics/img/logo.gif" alt="Just.Trades" />
              </div>
            </Link>
            <Link to="/" className="simple-text logo-normal">
              Just.Trades
            </Link>
          </div>
          <ul className="nav">
            <li className={isActive('/dashboard') ? 'active' : ''}>
              <Link to="/dashboard">
                <i className="material-icons">dashboard</i>
                <p>Dashboard</p>
              </Link>
            </li>
            <li className={isActive('/recorders') ? 'active' : ''}>
              <Link to="/recorders">
                <i className="material-icons">edit</i>
                <p>My Recorders</p>
              </Link>
            </li>
            <li className={isActive('/trader') ? 'active' : ''}>
              <a href="#trader" data-toggle="collapse" aria-expanded={isActive('/trader')}>
                <i className="material-icons">trending_up</i>
                <p>Trader<b className="caret">▼</b></p>
              </a>
              <div className={`collapse ${isActive('/trader') ? 'show' : ''}`}>
                <ul className="nav">
                  <li className={isActive('/trader/accounts') ? 'active' : ''}>
                    <Link to="/trader/accounts">
                      <span className="sidebar-mini-icon">AM</span>
                      <span className="sidebar-normal">Account Management</span>
                    </Link>
                  </li>
                  <li className={isActive('/trader/strategies') ? 'active' : ''}>
                    <Link to="/trader/strategies">
                      <span className="sidebar-mini-icon">MT</span>
                      <span className="sidebar-normal">My Traders</span>
                    </Link>
                  </li>
                  <li className={isActive('/trader/control-center') ? 'active' : ''}>
                    <Link to="/trader/control-center">
                      <span className="sidebar-mini-icon">CC</span>
                      <span className="sidebar-normal">Control Center</span>
                    </Link>
                  </li>
                </ul>
              </div>
            </li>
            <li className={isActive('/settings') ? 'active' : ''}>
              <Link to="/settings">
                <i className="material-icons">settings</i>
                <p>Settings</p>
              </Link>
            </li>
          </ul>
        </div>
      </div>

      {/* Main Panel */}
      <div className="main-panel">
        {/* Navbar */}
        <nav className="navbar-absolute navbar navbar-expand-lg">
          <div className="container-fluid">
            <div className="navbar-wrapper">
              <div className="navbar-minimize d-inline">
                <button
                  type="button"
                  className="minimize-sidebar btn-just-icon btn btn-link"
                  onClick={toggleSidebar}
                >
                  <i className="material-icons visible-on-sidebar-regular">menu</i>
                  <i className="material-icons visible-on-sidebar-mini">reorder</i>
                </button>
              </div>
              <div className="navbar-toggle d-inline">
                <button className="navbar-toggler" type="button">
                  <span className="navbar-toggler-bar bar1"></span>
                  <span className="navbar-toggler-bar bar2"></span>
                  <span className="navbar-toggler-bar bar3"></span>
                </button>
              </div>
              <a href="#" className="navbar-brand">
                {getPageTitle(location.pathname)}
              </a>
            </div>
            <div className="collapse navbar-collapse">
              <ul className="ml-auto d-flex align-items-center gap-3 navbar-nav">
                <span className="navbar-time text-white font-weight-bold d-none d-md-inline">
                  {currentTime}
                </span>
                <li className="nav-item">
                  <button
                    type="button"
                    id="darkModeToggle"
                    className="btn-icon btn-round btn btn-dark"
                    onClick={toggleDarkMode}
                    aria-label="Toggle dark mode"
                  >
                    <svg
                      stroke="currentColor"
                      fill="currentColor"
                      strokeWidth="0"
                      viewBox="0 0 512 512"
                      height="1em"
                      width="1em"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path d="M283.211 512c78.962 0 151.079-35.925 198.857-94.792 7.068-8.708-.639-21.43-11.562-19.35-124.203 23.654-238.262-71.576-238.262-196.954 0-72.222 38.662-138.635 101.498-174.394 9.686-5.512 7.25-20.197-3.756-22.23A258.156 258.156 0 0 0 283.211 0c-141.309 0-256 114.511-256 256 0 141.309 114.511 256 256 256z"></path>
                    </svg>
                  </button>
                </li>
                <li className={`dropdown nav-item ${dropdownOpen ? 'show' : ''}`}>
                  <a
                    href="#"
                    className="d-flex align-items-center p-0 dropdown-toggle nav-link"
                    onClick={(e) => {
                      e.preventDefault();
                      toggleDropdown();
                    }}
                    aria-haspopup="true"
                    aria-expanded={dropdownOpen}
                  >
                    <img
                      alt="User avatar"
                      src="/client_specifics/img/logo.gif"
                      className="rounded-circle user-avatar"
                    />
                    <span className="ml-2 text-white font-weight-bold d-none d-md-inline" style={{ fontSize: '0.875rem' }}>
                      {user?.username || 'User'}
                    </span>
                    <i className="material-icons ml-1 d-none d-md-inline" style={{ fontSize: '16px', opacity: 0.7 }}>arrow_drop_down</i>
                  </a>
                  <div className={`dropdown-dark dropdown-menu dropdown-menu-right ${dropdownOpen ? 'show' : ''}`}>
                    <button
                      type="button"
                      className="dropdown-item"
                      onClick={(e) => {
                        e.preventDefault();
                        setDropdownOpen(false);
                        logout();
                      }}
                      role="menuitem"
                    >
                      Log out
                    </button>
                  </div>
                </li>
                <li className="separator d-lg-none"></li>
              </ul>
            </div>
          </div>
        </nav>

        {/* Content */}
        <div className="content">{children}</div>

        {/* Footer */}
        <footer className="footer">
          <div className="container-fluid"></div>
        </footer>
      </div>
    </div>
  );
};

export default Layout;

