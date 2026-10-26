import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../lib/api";
import { getDeviceId } from "../lib/device";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const check = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (error) {
      const status = error?.response?.status;
      if (status === 401 || status === 403) setUser(false);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  useEffect(() => {
    if (user !== null) return undefined;
    const retry = setInterval(check, 8000);
    return () => clearInterval(retry);
  }, [user, check]);

  useEffect(() => {
    const onReplaced = () => {
      setUser((u) => {
        if (u) toast.error("You were logged out because your account was signed in on another device.");
        return false;
      });
    };
    const onBanned = (e) => {
      setUser(false);
      toast.error(e.detail);
    };
    const onExpired = () => {
      setUser(false);
      toast.error("Your session has expired. Please log in again.");
    };
    window.addEventListener("joblens:session-replaced", onReplaced);
    window.addEventListener("joblens:banned", onBanned);
    window.addEventListener("joblens:auth-expired", onExpired);
    return () => {
      window.removeEventListener("joblens:session-replaced", onReplaced);
      window.removeEventListener("joblens:banned", onBanned);
      window.removeEventListener("joblens:auth-expired", onExpired);
    };
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    const t = setInterval(() => api.get("/auth/me").catch(() => {}), 15000);
    const onFocus = () => api.get("/auth/me").catch(() => {});
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
    };
  }, [user]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password, device_id: await getDeviceId() });
    setUser(data);
    return data;
  };

  const register = async (name, email, password) => {
    const { data } = await api.post("/auth/register", { name, email, password, device_id: await getDeviceId() });
    setUser(data);
    return data;
  };

  const logout = async () => {
    await api.post("/auth/logout").catch(() => {});
    setUser(false);
  };

  return <AuthCtx.Provider value={{ user, login, register, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
