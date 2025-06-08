import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { User } from '../../../shared/types'; // Import User from shared types

// Define the shape of the AuthContext
interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  login: (email_param: string, password_param: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

// Create the AuthContext
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Helper function to parse JWT
// In a real app, you might use a library like jwt-decode
const parseJwt = (token: string): Omit<User, 'id'> | null => { // JWT might not contain all User fields like 'id'
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join('')
    );
    const decoded = JSON.parse(jsonPayload);
    // Ensure role is one of the allowed types or handle appropriately
    const role = decoded.role as User['role'];
    // TODO: Add validation or default for role if it doesn't match shared type
    return { email: decoded.sub, role: role };
  } catch (e) {
    console.error('Failed to parse JWT:', e);
    return null;
  }
};

// Create the AuthProvider component
export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('accessToken'));
  const [user, setUser] = useState<Omit<User, 'id'> | null>(null); // User object might be partial from JWT
  const [isLoading, setIsLoading] = useState<boolean>(true); // To check auth status on initial load
  const navigate = useNavigate();

  useEffect(() => {
    const storedToken = localStorage.getItem('accessToken');
    if (storedToken) {
      const parsedUser = parseJwt(storedToken);
      if (parsedUser) {
        setUser(parsedUser);
        setToken(storedToken);
        axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
      } else {
        // Invalid token
        localStorage.removeItem('accessToken');
        setToken(null);
        setUser(null);
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (email_param: string, password_param: string) => {
    setIsLoading(true);
    try {
      const response = await axios.post(
        'http://localhost:8000/auth/login/access-token',
        new URLSearchParams({
          username: email_param,
          password: password_param,
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );
      const { access_token } = response.data;
      localStorage.setItem('accessToken', access_token);
      const parsedUser = parseJwt(access_token);
      setUser(parsedUser);
      setToken(access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      navigate('/datasources'); // Redirect to a protected page
    } catch (error) {
      console.error('Login failed:', error);
      if (axios.isAxiosError(error) && error.response) {
        throw new Error(error.response.data.detail || 'Login failed');
      }
      throw new Error('Login failed due to an unexpected error.');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('accessToken');
    setUser(null);
    setToken(null);
    delete axios.defaults.headers.common['Authorization'];
    navigate('/login');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token && !!user, user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

// Create a custom hook to use the AuthContext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
