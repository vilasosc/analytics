import React, { useState } from 'react';
// useNavigate is already imported if needed elsewhere, but login now handles navigation
import { Box, Button, FormControl, FormLabel, Input, VStack, Heading, Text, Spinner } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { login, isLoading } = useAuth();
  // const navigate = useNavigate(); // Not needed directly if login handles navigation

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await login(email, password);
      // Navigation is handled by the login function in AuthContext upon success
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    }
  };

  return (
    <Box display="flex" alignItems="center" justifyContent="center" minHeight="calc(100vh - 120px)"> {/* Adjust height based on header/footer */}
      <VStack spacing={4} p={8} boxShadow="md" borderRadius="md" bg="white">
        <Heading as="h2" size="lg">Login</Heading>
        <form onSubmit={handleSubmit} style={{ width: '100%' }}>
          <VStack spacing={4}>
            <FormControl id="email" isDisabled={isLoading}>
              <FormLabel>Email address</FormLabel>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </FormControl>
            <FormControl id="password" isDisabled={isLoading}>
              <FormLabel>Password</FormLabel>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </FormControl>
            {error && <Text color="red.500" textAlign="center">{error}</Text>}
            <Button type="submit" colorScheme="blue" width="full" isLoading={isLoading}>
              {isLoading ? <Spinner size="sm" /> : 'Login'}
            </Button>
          </VStack>
        </form>
      </VStack>
    </Box>
  );
};

export default LoginPage;
