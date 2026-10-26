import React, { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Building2, Briefcase, ShieldAlert, ClipboardCheck, LayoutDashboard, LogOut, Menu, Mic, ScanLine, Upload, UserCog, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useUIMode } from "../context/UIMode";
import AlertsBell from "./AlertsBell";

const LINKS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/mock-oa", label: "Mock OA", icon: ClipboardCheck },
  { to: "/accenture-mocks", label: "Accenture", icon: Building2 },
  { to: "/interview", label: "AI Interview", icon: Mic },
  { to: "/profile", label: "Profile", icon: UserCog },
];
const ADMIN_LINK = { to: "/admin", label: "Admin", icon: ShieldAlert };

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2" data-testid="nav-logo">
      <span className="flex h-10 w-10 items-center justify-center bg-ink text-brand-yellow shadow-brutalsm"><ScanLine size={22} /></span>
      <span className="font-display text-xl font-bold">JobLens <span className="text-brand-blue">AI</span></span>
    </Link>
  );
}

function ProfileMenu({ user }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { logout } = useAuth();
  const nav = useNavigate();
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="brutal-btn bg-brand-yellow px-3 py-2" data-testid="profile-chip">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-sm text-white">{user.name[0]?.toUpperCase()}</span>
        <span className="hidden sm:inline">{user.name.split(" ")[0]}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="brutal-card absolute right-0 mt-3 w-60 p-2 z-50">
            <p className="px-3 py-2 font-mono text-xs text-ink/60 truncate">{user.email}</p>
            <button onClick={() => { setOpen(false); nav("/upload"); }} className="flex w-full items-center gap-2 px-3 py-2 font-display font-semibold hover:bg-offwhite" data-testid="menu-reupload">
              <Upload size={16} /> Upload new resume
            </button>
            <button onClick={async () => { await logout(); nav("/login"); }} className="flex w-full items-center gap-2 px-3 py-2 font-display font-semibold text-brand-red hover:bg-offwhite" data-testid="menu-logout">
              <LogOut size={16} /> Log out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const linkCls = ({ isActive }) =>
  `flex items-center gap-2 px-4 py-2 font-display font-semibold transition-colors ${isActive ? "bg-ink text-white shadow-brutalsm" : "hover:bg-offwhite"}`;

export default function Navbar() {
  const { user } = useAuth();
  const { focusMode } = useUIMode();
  const [mob, setMob] = useState(false);
  const links = user?.role === "admin" ? [...LINKS, ADMIN_LINK] : LINKS;
  if (focusMode) {
    return (
      <header className="sticky top-0 z-40 border-b-3 border-ink bg-paper/95 backdrop-blur" data-testid="navbar-focus">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 md:px-8 py-3">
          <Logo />
          <span className="flex items-center gap-2 border-2 border-ink bg-brand-yellow px-3 py-1.5 font-display text-xs font-bold" data-testid="focus-badge">
            <ScanLine size={14} /> Assessment in progress
          </span>
        </div>
      </header>
    );
  }
  return (
    <header className="sticky top-0 z-40 border-b-3 border-ink bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 md:px-8 py-3">
        <Logo />
        {user && (
          <nav className="hidden md:flex items-center gap-1">
            {links.map(({ to, label, icon: I }) => (
              <NavLink key={to} to={to} className={linkCls} data-testid={`nav-${label.toLowerCase().replace(" ", "-")}`}>
                <I size={17} /> {label}
              </NavLink>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-2">
          {user ? <><AlertsBell /><ProfileMenu user={user} /></> : (
            <>
              <Link to="/login" className="brutal-btn bg-white px-4 py-2" data-testid="nav-login">Log in</Link>
              <Link to="/register" className="brutal-btn bg-ink text-white px-4 py-2" data-testid="nav-register">Sign up</Link>
            </>
          )}
          {user && (
            <button className="md:hidden border-3 border-ink p-2 bg-white" onClick={() => setMob(!mob)} data-testid="mobile-menu-toggle">
              {mob ? <X size={18} /> : <Menu size={18} />}
            </button>
          )}
        </div>
      </div>
      {user && mob && (
        <nav className="md:hidden border-t-3 border-ink bg-paper px-4 py-3 flex flex-col gap-1">
          {links.map(({ to, label, icon: I }) => (
            <NavLink key={to} to={to} className={linkCls} data-testid={`mobile-nav-${label.toLowerCase().replace(" ", "-")}`} onClick={() => setMob(false)}><I size={17} /> {label}</NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
