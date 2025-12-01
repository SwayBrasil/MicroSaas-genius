// src/App.tsx
import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import HeaderApp from "./components/AppHeader";
import { ProtectedRoute } from "./ProtectedRoute";
import Chat from "./pages/Chat";
import Contacts from "./pages/Contacts";
import Dashboard from "./pages/Dashboard";
import Kanban from "./pages/Kanban";
import Tasks from "./pages/Tasks";
import Profile from "./pages/Profile";
import Login from "./pages/Login";
import Audios from "./pages/Audios";
import Automations from "./pages/Automations";
import { useDarkMode } from "./hooks/useDarkMode";
import "./styles.css"; // ✅ garante que o CSS global está carregado

// Componente wrapper para inicializar o tema
function ThemeInitializer({ children }: { children: React.ReactNode }) {
  useDarkMode(); // Inicializa o tema (aplica no mount)
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeInitializer>
      <div className="layout" style={{ 
        minHeight: "100vh", 
        maxHeight: "100vh",
        maxWidth: "100vw",
        width: "100vw",
        height: "100vh",
        display: "flex", 
        flexDirection: "column",
        overflow: "hidden",
        boxSizing: "border-box",
        position: "relative",
      }}>
        <Routes>
          {/* Login público */}
          <Route path="/login" element={<Login />} />

          {/* Chat - sem header, layout próprio tipo WhatsApp */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />

          {/* Conversas */}
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />

          {/* Outras páginas - com header */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ 
                    flex: 1, 
                    maxWidth: "100%", 
                    margin: "0 auto", 
                    width: "100%", 
                    padding: "14px",
                    overflow: "auto",
                    boxSizing: "border-box"
                  }}>
                    <Dashboard />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/contacts"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Contacts />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/kanban"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Kanban />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Tasks />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Profile />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/audios"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Audios />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          <Route
            path="/automations"
            element={
              <ProtectedRoute>
                <>
                  <HeaderApp />
                  <div style={{ flex: 1, maxWidth: 1100, margin: "0 auto", width: "100%", padding: 14 }}>
                    <Automations />
                  </div>
                </>
              </ProtectedRoute>
            }
          />

          {/* fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </ThemeInitializer>
  );
}
