import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import MyDataPage from "./pages/MyDataPage";
import CalendarPage from "./pages/CalendarPage";
import SupplementsPage from "./pages/SupplementsPage";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";

const TABS = [
  { to: "/dashboard", label: "대시보드", icon: "🏠" },
  { to: "/data", label: "내 데이터", icon: "📊" },
  { to: "/calendar", label: "캘린더", icon: "📅" },
  { to: "/supplements", label: "영양제", icon: "💊" },
  { to: "/chat", label: "채팅", icon: "💬" },
  { to: "/report", label: "리포트", icon: "📄" },
];

function TabBar() {
  return (
    <nav className="fixed bottom-0 inset-x-0 bg-white/90 backdrop-blur border-t border-stone-200">
      <div className="max-w-lg mx-auto flex">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center py-2 text-xs min-h-11 transition-colors ${
                isActive ? "text-teal-700 font-semibold" : "text-slate-400"
              }`
            }
          >
            <span className="text-lg leading-none">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-stone-50 pb-20 text-slate-800">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/data" element={<MyDataPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/supplements" element={<SupplementsPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        <TabBar />
      </div>
    </BrowserRouter>
  );
}
