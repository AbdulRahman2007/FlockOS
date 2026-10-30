import axios from 'axios';

export function getLoginError(
  error: unknown,
): 'invalid' | 'rate_limited' | 'unavailable' {
  if (axios.isAxiosError(error) && error.response?.status === 429)
    return 'rate_limited';
  if (axios.isAxiosError(error) && error.response?.status === 401)
    return 'invalid';
  return 'unavailable';
}
