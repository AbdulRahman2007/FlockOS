import { useAuth } from '../context/useAuth';

export function useRole(): string | null {
  const { token } = useAuth();
  if (!token) return null;
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const encoded = payload.replace(/-/g, '+').replace(/_/g, '/');
    return (JSON.parse(atob(encoded)) as { role?: string }).role ?? null;
  } catch {
    return null;
  }
}
