import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  useToast,
  HStack,
  IconButton,
  Flex,
  Spacer,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Tooltip, // Import Tooltip
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon, ViewIcon } from '@chakra-ui/icons';
import { useDisclosure } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom'; // Import useNavigate
import dataSourceService, { DataSourceResponse } from '../services/dataSourceService';
import DataSourceForm from '../components/DataSources/DataSourceForm';

const DataSourcesPage: React.FC = () => {
  const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { isOpen: isFormOpen, onOpen: onFormOpen, onClose: onFormClose } = useDisclosure();
  const { isOpen: isAlertOpen, onOpen: onAlertOpen, onClose: onAlertClose } = useDisclosure();
  const [editingDataSource, setEditingDataSource] = useState<DataSourceResponse | null>(null);
  const [deletingDataSourceId, setDeletingDataSourceId] = useState<string | number | null>(null);
  const cancelRef = React.useRef<HTMLButtonElement>(null); // For AlertDialog
  const toast = useToast();
  const navigate = useNavigate(); // Initialize useNavigate

  const fetchDataSources = async () => {
    // setIsLoading(true); // Keep true if it's a full page refresh
    setError(null);
    try {
      const data = await dataSourceService.getAllDataSources();
      setDataSources(data);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch data sources';
      setError(errorMessage);
      toast({
        title: 'Error fetching data sources',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDataSources();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Added comment to satisfy potential linter rule, toast is stable, fetchDataSources is memoized by being part of component.

  const handleCreateNew = () => {
    setEditingDataSource(null);
    onFormOpen();
  };

  const handleEdit = (dataSource: DataSourceResponse) => {
    setEditingDataSource(dataSource);
    onFormOpen();
  };

  const handleFormSave = (savedDataSource: DataSourceResponse) => {
    fetchDataSources(); // Refresh the list
    // The form itself calls onFormClose, but if it didn't, you'd call it here.
  };

  const handleFormClose = () => {
    setEditingDataSource(null);
    onFormClose();
  }

  const handleDeleteInitiate = (id: number | string) => {
    setDeletingDataSourceId(id);
    onAlertOpen();
  };

  const handleDeleteConfirm = async () => {
    if (deletingDataSourceId) {
      try {
        await dataSourceService.deleteDataSource(deletingDataSourceId);
        toast({
          title: 'Data Source Deleted',
          description: `Data Source (ID: ${deletingDataSourceId}) was successfully deleted.`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        fetchDataSources(); // Refresh list
      } catch (err: any) {
        const message = err.response?.data?.detail || err.message || 'Failed to delete data source.';
        toast({
          title: 'Delete Error',
          description: message,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        setDeletingDataSourceId(null);
        onAlertClose();
      }
    }
  };

  const handleViewDetails = (id: number | string) => {
    navigate(`/datasources/${id}/metadata`);
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <Spinner size="xl" />
      </Box>
    );
  }

  if (error && dataSources.length === 0) { // Only show full page error if no data is available
    return (
      <Box textAlign="center" mt={10}>
        <Text color="red.500" fontSize="lg">Error: {error}</Text>
        <Button onClick={fetchDataSources} mt={4}>Retry</Button>
      </Box>
    );
  }

  return (
    <Box p={4}>
      <Flex mb={6} align="center">
        <Heading as="h2" size="lg">Data Sources</Heading>
        <Spacer />
        <Button leftIcon={<AddIcon />} colorScheme="blue" onClick={handleCreateNew}>
          Create New Data Source
        </Button>
      </Flex>

      {error && ( // Display error as a toast or inline message even if some data might be stale/shown
         <Text color="red.500" mb={4}>Error fetching latest data: {error}. Displaying cached or older data if available.</Text>
      )}

      {dataSources.length === 0 && !isLoading && !error && (
        <Text>No data sources found. Click "Create New Data Source" to add one.</Text>
      )}

      {dataSources.length > 0 && (
        <Table variant="simple" boxShadow="md" borderRadius="md">
          <Thead bg="gray.50">
            <Tr>
              <Th>Name</Th>
              <Th>Type</Th>
              <Th>Host</Th>
              <Th>Database Name</Th>
              <Th>Actions</Th>
            </Tr>
          </Thead>
          <Tbody>
            {dataSources.map((ds) => (
              <Tr key={ds.id}>
                <Td>{ds.name}</Td>
                <Td>{ds.type}</Td>
                <Td>{ds.db_host || 'N/A'}</Td>
                <Td>{ds.db_name || 'N/A'}</Td>
                <Td>
                  <HStack spacing={2}>
                    <Tooltip label="Edit Data Source">
                      <IconButton
                        icon={<EditIcon />}
                        aria-label="Edit Data Source"
                        onClick={() => handleEdit(ds)} // Pass the whole ds object
                        size="sm"
                        colorScheme="yellow"
                      />
                    </Tooltip>
                    <Tooltip label="Delete Data Source">
                      <IconButton
                        icon={<DeleteIcon />}
                        aria-label="Delete Data Source"
                        onClick={() => handleDeleteInitiate(ds.id)}
                        size="sm"
                        colorScheme="red"
                      />
                    </Tooltip>
                    <Tooltip label="Manage Metadata / View Details">
                      <IconButton
                        icon={<ViewIcon />}
                        aria-label="View Details"
                        onClick={() => handleViewDetails(ds.id)}
                        size="sm"
                        colorScheme="green"
                      />
                    </Tooltip>
                  </HStack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}

      {isFormOpen && (
        <DataSourceForm
          isOpen={isFormOpen}
          onClose={handleFormClose}
          onSave={handleFormSave}
          initialData={editingDataSource}
        />
      )}

      <AlertDialog
        isOpen={isAlertOpen}
        leastDestructiveRef={cancelRef}
        onClose={onAlertClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Data Source
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete Data Source (ID: {deletingDataSourceId})? This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onAlertClose}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={handleDeleteConfirm} ml={3}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default DataSourcesPage;
