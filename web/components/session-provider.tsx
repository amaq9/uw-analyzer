"use client";

import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import { getCurrentUser, type CurrentUser } from "@/lib/api/client";

export type UserSession = {
  token: string;
  user: CurrentUser;
};

type SessionContextValue = {
  session?: UserSession;
  signIn: (token: string) => Promise<CurrentUser>;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [session, setSession] = useState<UserSession>();

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      async signIn(token) {
        const user = await getCurrentUser(token);
        setSession({ token, user });
        return user;
      },
      signOut() {
        setSession(undefined);
      },
    }),
    [session],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);

  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }

  return context;
}
