import React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Toaster } from "sonner";
import Navbar from "./components/Navbar";
import AIStatusBanner from "./components/AIStatusBanner";
import { FullLoader } from "./components/Loaders";
import { useAuth } from "./context/AuthContext";
import Landing from "./pages/Landing";
import AuthPage from "./pages/AuthPage";
import UploadPage from "./pages/UploadPage";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import Jobs from "./pages/Jobs";
import JobDetails from "./pages/JobDetails";
import MockOA from "./pages/MockOA";
import AIInterview from "./pages/AIInterview";
import Alerts from "./pages/Alerts";
import Admin from "./pages/Admin";
import AccentureMocks from "./pages/AccentureMocks";
import AccentureGamified from "./pages/AccentureGamified";
import AccentureBehavioural from "./pages/AccentureBehavioural";
import AccentureTechnical from "./pages/AccentureTechnical";
import AccentureCoding from "./pages/AccentureCoding";
import { AccProctorProvider, ProctoredRound } from "./components/accenture/ProctorGate";

function Protected({ children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null) return <FullLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return children;
}

function AdminOnly({ children }) {
  const { user } = useAuth();
  return user && user.role !== "admin" ? <Navigate to="/dashboard" replace /> : children;
}

function GuestOnly({ children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  return user ? <Navigate to="/dashboard" replace /> : children;
}

const Page = ({ children }) => (
  <motion.main initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
    {children}
  </motion.main>
);

export default function App() {
  const loc = useLocation();
  const p = (el) => <Protected><Page>{el}</Page></Protected>;
  return (
    <div className="min-h-screen">
      <Navbar />
      <AIStatusBanner />
      <Toaster position="top-center" toastOptions={{ className: "!border-3 !border-ink !rounded-none !shadow-brutal !font-display" }} />
      <AccProctorProvider>
      <AnimatePresence mode="wait">
        <Routes location={loc} key={loc.pathname}>
          <Route path="/" element={<GuestOnly><Page><Landing /></Page></GuestOnly>} />
          <Route path="/login" element={<GuestOnly><Page><AuthPage mode="login" /></Page></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><Page><AuthPage mode="register" /></Page></GuestOnly>} />
          <Route path="/upload" element={p(<UploadPage />)} />
          <Route path="/dashboard" element={p(<Dashboard />)} />
          <Route path="/jobs" element={p(<Jobs />)} />
          <Route path="/jobs/:id" element={p(<JobDetails />)} />
          <Route path="/mock-oa" element={p(<MockOA />)} />
          <Route path="/accenture-mocks" element={p(<AccentureMocks />)} />
          <Route path="/accenture-mocks/:mockId/behavioural" element={p(<ProctoredRound round="behavioural"><AccentureBehavioural /></ProctoredRound>)} />
          <Route path="/accenture-mocks/:mockId/gamified" element={p(<ProctoredRound round="gamified"><AccentureGamified /></ProctoredRound>)} />
          <Route path="/accenture-mocks/:mockId/technical" element={p(<ProctoredRound round="technical"><AccentureTechnical /></ProctoredRound>)} />
          <Route path="/accenture-mocks/:mockId/coding" element={p(<ProctoredRound round="coding"><AccentureCoding /></ProctoredRound>)} />
          <Route path="/interview" element={p(<AIInterview />)} />
          <Route path="/alerts" element={p(<Alerts />)} />
          <Route path="/profile" element={p(<Profile />)} />
          <Route path="/admin" element={p(<AdminOnly><Admin /></AdminOnly>)} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
      </AccProctorProvider>
    </div>
  );
}
