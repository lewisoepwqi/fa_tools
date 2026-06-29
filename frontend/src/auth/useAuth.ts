import { useContext } from 'react';
import { AuthContext } from './AuthProvider';

/** 消费鉴权上下文。须在 <AuthProvider> 内部使用。 */
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);
