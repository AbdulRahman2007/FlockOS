import { createContext } from 'react';

export type AuthValue = {
  ready: boolean;
  authenticated: boolean;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthValue | null>(null);
