import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../services/api';
import { AuthContext } from './authContextValue';

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const refreshStarted = useRef(false);

  const accept = useCallback((response: TokenResponse) => {
    setToken(response.access_token);
    api.defaults.headers.common.Authorization = `Bearer ${response.access_token}`;
  }, []);

  useEffect(() => {
    if (refreshStarted.current) return;
    refreshStarted.current = true;
    void api
      .post<TokenResponse>('/auth/refresh')
      .then(({ data }) => accept(data))
      .catch(() => {
        setToken(null);
      })
      .finally(() => setReady(true));
  }, [accept]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await api.post<TokenResponse>('/auth/login', {
        email,
        password,
      });
      accept(data);
    },
    [accept],
  );

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout', undefined, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
    } finally {
      setToken(null);
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  const value = useMemo(
    () => ({ ready, authenticated: token !== null, token, login, logout }),
    [ready, token, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
