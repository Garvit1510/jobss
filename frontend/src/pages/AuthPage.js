import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Lock, Mail, ShieldCheck, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errMsg } from "../lib/api";
import { Button, Spinner } from "../components/ui";

function Field({ icon: I, ...p }) {
  return (
    <label className="relative block">
      <I size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink/50" />
      <input className="brutal-input pl-11" {...p} />
    </label>
  );
}

export default function AuthPage({ mode }) {
  const isReg = mode === "register";
  const { login, register } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (isReg && f.password.length < 8) return setErr("Password must be at least 8 characters.");
    setBusy(true);
    try {
      if (isReg) await register(f.name, f.email, f.password);
      else await login(f.email, f.password);
      nav(isReg ? "/upload" : loc.state?.from || "/dashboard", { replace: true });
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 md:py-24">
      <form onSubmit={submit} className="brutal-card p-8 shadow-brutallg" data-testid={`${mode}-form`}>
        <p className="eyebrow mb-2">{isReg ? "Create account" : "Welcome back"}</p>
        <h1 className="text-4xl font-bold mb-8">{isReg ? "Join JobLens AI" : "Log in"}</h1>
        <div className="space-y-4">
          {isReg && <Field icon={User} placeholder="Full name" value={f.name} onChange={set("name")} required minLength={2} data-testid="auth-name-input" />}
          <Field icon={Mail} type="email" placeholder="Email" value={f.email} onChange={set("email")} required data-testid="auth-email-input" />
          <Field icon={Lock} type="password" placeholder={isReg ? "Password (min 8 characters)" : "Password"} value={f.password} onChange={set("password")} required data-testid="auth-password-input" />
        </div>
        {err && <p className="mt-4 border-2 border-ink bg-brand-red/15 px-3 py-2 text-sm font-medium" data-testid="auth-error">{err}</p>}
        <Button variant="primary" className="mt-6 w-full py-3.5 text-lg" disabled={busy} data-testid="auth-submit-button">
          {busy ? <Spinner /> : <>{isReg ? "Create account" : "Log in"} <ArrowRight size={18} /></>}
        </Button>
        <p className="mt-6 text-center text-sm">
          {isReg ? "Already have an account? " : "New to JobLens AI? "}
          <Link to={isReg ? "/login" : "/register"} className="font-bold underline decoration-brand-blue decoration-2 underline-offset-4" data-testid="auth-switch-link">
            {isReg ? "Log in" : "Create one"}
          </Link>
        </p>
        <p className="mt-6 flex items-start gap-2 border-t-2 border-ink/10 pt-4 text-xs text-ink/60">
          <ShieldCheck size={16} className="shrink-0 text-brand-green" />
          One account per device. Your account stays signed in on one device at a time — signing in elsewhere logs out the other device.
        </p>
      </form>
    </div>
  );
}
