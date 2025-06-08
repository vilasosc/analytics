import React from 'react';
import { ChakraProvider, Box, Text, VStack } from '@chakra-ui/react';
import theme from './theme'; // Will be created next

function App() {
  return (
    <ChakraProvider theme={theme}>
      <Box textAlign="center" fontSize="xl">
        <VStack spacing={8} mt={20}>
          <Text fontSize="4xl" fontWeight="bold">
            PCSoft Analytics
          </Text>
          <Text>Frontend Application - Under Construction</Text>
        </VStack>
      </Box>
    </ChakraProvider>
  );
}

export default App;
