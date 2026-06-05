import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import { api, clearTokens, getAccess, getRefresh, setTokens } from "./api";
import type { Org, User } from "./types";

interface AuthValue {
  user: User | null;
  orgs: Org[];
  org: Org | null; // default (first) org
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const Ctx = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    try {
      const me = await api<{ user: User; orgs: Org[] }>("/auth/me");
      setUser(me.user);
      setOrgs(me.orgs);
    } catch {
      setUser(null);
      setOrgs([]);
    }
  }

  useEffect(() => {
    (async () => {
      if (getAccess()) await loadMe();
      setLoading(false);
    })();
  }, []);

  async function login(email: string, password: string) {
    setTokens(await api("/auth/login", { method: "POST", body: { email, password }, auth: false }));
    await loadMe();
  }

  async function register(email: string, password: string, fullName?: string) {
    setTokens(
      await api("/auth/register", {
        method: "POST",
        body: { email, password, full_name: fullName },
        auth: false,
      }),
    );
    await loadMe();
  }

  async function logout() {
    const refresh = getRefresh();
    try {
      if (refresh) await api("/auth/logout", { method: "POST", body: { refresh_token: refresh }, auth: false });
    } catch {
      /* ignore */
    }
    clearTokens();
    setUser(null);
    setOrgs([]);
  }

  const value: AuthValue = {
    user,
    orgs,
    org: orgs[0] ?? null,
    loading,
    login,
    register,
    logout,
    reload: loadMe,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(Ctx);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
