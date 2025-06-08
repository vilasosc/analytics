import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Box, Button, Heading, Flex, Spacer } from '@chakra-ui/react';

const Header: React.FC = () => {
  const { isAuthenticated, logout, user } = useAuth();

  return (
    <Box as="header" borderBottom="1px solid #ccc" p={4} backgroundColor="#f0f0f0">
      <Flex align="center">
        <Heading as="h1" size="md">Data Catalog</Heading>
        <Spacer />
        {isAuthenticated && (
          <Flex align="center">
            {user && <Text mr={4}>Welcome, {user.email}</Text>}
            <Button colorScheme="blue" onClick={logout}>Logout</Button>
          </Flex>
        )}
      </Flex>
    </Box>
  );
};

export default Header;
