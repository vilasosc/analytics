import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Select,
  Button,
  VStack,
  useToast,
  Spinner,
  Text,
  Box
} from '@chakra-ui/react';
import dataSourceService, { DataSourceCreate, DataSourceUpdate, TestConnectionRequest } from '../../services/dataSourceService';
import { DataSourceResponse } from '../../services/dataSourceService'; // Re-export or use from service
import { DataSourceType } from '../../../../shared/types'; // Correct path to shared types

interface DataSourceFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (dataSource: DataSourceResponse) => void; // Callback after successful save
  initialData?: DataSourceResponse | null; // For pre-filling form in edit mode
}

const DataSourceForm: React.FC<DataSourceFormProps> = ({ isOpen, onClose, onSave, initialData }) => {
  const [formData, setFormData] = useState<DataSourceCreate | DataSourceUpdate>({
    name: '',
    type: DataSourceType.SQLSERVER, // Default type
    db_host: '',
    db_port: undefined,
    db_name: '',
    db_username: '',
    db_password: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [testConnectionResult, setTestConnectionResult] = useState<{ message: string; connected: boolean } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const toast = useToast();

  const isEditMode = !!initialData;

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name,
        type: initialData.type,
        db_host: initialData.db_host || '',
        db_port: initialData.db_port || undefined,
        db_name: initialData.db_name || '',
        db_username: initialData.db_username || '',
        db_password: '', // Password is not pre-filled for security
      });
    } else {
      // Reset form for create mode
      setFormData({
        name: '',
        type: DataSourceType.SQLSERVER,
        db_host: '',
        db_port: undefined,
        db_name: '',
        db_username: '',
        db_password: '',
      });
    }
    setTestConnectionResult(null); // Reset test connection result when form opens/initialData changes
    setErrors({});
  }, [initialData, isOpen]); // Depend on isOpen to reset form when reopened

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'db_port' ? (value ? parseInt(value, 10) : undefined) : value,
    }));
    setErrors((prev) => ({ ...prev, [name]: '' })); // Clear error for this field
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = 'Name is required.';
    if (!formData.type) newErrors.type = 'Type is required.';
    // Add other validations as needed (e.g., for host, port if type requires them)
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleTestConnection = async () => {
    if (!validateForm()) {
        toast({ title: "Validation Error", description: "Please fill all required fields before testing.", status: "warning", duration: 3000, isClosable: true });
        return;
    }
    setIsTestingConnection(true);
    setTestConnectionResult(null);
    try {
      // Ensure all fields for TestConnectionRequest are present
      const testData: TestConnectionRequest = {
        name: formData.name, // Name is not strictly needed for test, but API might expect it
        type: formData.type,
        db_host: formData.db_host,
        db_port: formData.db_port,
        db_name: formData.db_name,
        db_username: formData.db_username,
        db_password: formData.db_password,
      };
      const result = await dataSourceService.testDataSourceConnection(testData);
      setTestConnectionResult(result);
      toast({
        title: result.connected ? 'Connection Successful' : 'Connection Failed',
        description: result.message,
        status: result.connected ? 'success' : 'error',
        duration: 5000,
        isClosable: true,
      });
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Failed to test connection.';
      setTestConnectionResult({ message, connected: false });
      toast({
        title: 'Connection Test Error',
        description: message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validateForm()) return;

    setIsSaving(true);
    try {
      let savedDataSource: DataSourceResponse;
      if (isEditMode && initialData) {
        // Ensure db_password is only included if changed.
        // The backend schema for update might make password optional.
        const updatePayload: DataSourceUpdate = { ...formData };
        if (!formData.db_password) {
          delete updatePayload.db_password;
        }
        savedDataSource = await dataSourceService.updateDataSource(initialData.id, updatePayload);
        toast({ title: 'Data Source Updated', status: 'success', duration: 3000, isClosable: true });
      } else {
        savedDataSource = await dataSourceService.createDataSource(formData as DataSourceCreate);
        toast({ title: 'Data Source Created', status: 'success', duration: 3000, isClosable: true });
      }
      onSave(savedDataSource); // Callback to refresh list and potentially close modal
      onClose(); // Close modal on successful save
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Failed to save data source.';
      toast({ title: 'Save Error', description: message, status: 'error', duration: 5000, isClosable: true });
      // Potentially set form-level errors if applicable from response
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" closeOnOverlayClick={false}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{isEditMode ? 'Edit Data Source' : 'Create New Data Source'}</ModalHeader>
        <ModalCloseButton />
        <form onSubmit={handleSubmit}>
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired isInvalid={!!errors.name}>
                <FormLabel htmlFor="name">Name</FormLabel>
                <Input id="name" name="name" value={formData.name} onChange={handleChange} placeholder="e.g., My Production DB" />
                {errors.name && <Text color="red.500" fontSize="sm">{errors.name}</Text>}
              </FormControl>

              <FormControl isRequired isInvalid={!!errors.type}>
                <FormLabel htmlFor="type">Type</FormLabel>
                <Select id="type" name="type" value={formData.type} onChange={handleChange}>
                  {Object.values(DataSourceType).map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </Select>
                {errors.type && <Text color="red.500" fontSize="sm">{errors.type}</Text>}
              </FormControl>

              <FormControl>
                <FormLabel htmlFor="db_host">Host</FormLabel>
                <Input id="db_host" name="db_host" value={formData.db_host || ''} onChange={handleChange} placeholder="e.g., localhost or server.example.com" />
              </FormControl>

              <FormControl>
                <FormLabel htmlFor="db_port">Port</FormLabel>
                <Input id="db_port" name="db_port" type="number" value={formData.db_port || ''} onChange={handleChange} placeholder="e.g., 1433 (SQL Server), 5432 (PostgreSQL)" />
              </FormControl>

              <FormControl>
                <FormLabel htmlFor="db_name">Database Name</FormLabel>
                <Input id="db_name" name="db_name" value={formData.db_name || ''} onChange={handleChange} placeholder="e.g., AdventureWorks" />
              </FormControl>

              <FormControl>
                <FormLabel htmlFor="db_username">Username</FormLabel>
                <Input id="db_username" name="db_username" value={formData.db_username || ''} onChange={handleChange} placeholder="e.g., db_user" />
              </FormControl>

              <FormControl>
                <FormLabel htmlFor="db_password">Password</FormLabel>
                <Input
                  id="db_password"
                  name="db_password"
                  type="password"
                  value={formData.db_password || ''}
                  onChange={handleChange}
                  placeholder={isEditMode ? "Leave blank to keep unchanged" : ""}
                />
              </FormControl>

              {testConnectionResult && (
                <Box p={3} borderWidth="1px" borderRadius="md" bg={testConnectionResult.connected ? 'green.50' : 'red.50'} w="full">
                    <Text color={testConnectionResult.connected ? 'green.700' : 'red.700'} fontWeight="bold">
                        {testConnectionResult.connected ? 'Connection Successful' : 'Connection Failed'}
                    </Text>
                    <Text fontSize="sm" color={testConnectionResult.connected ? 'green.600' : 'red.600'}>
                        {testConnectionResult.message}
                    </Text>
                </Box>
              )}

            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button
              colorScheme="teal"
              onClick={handleTestConnection}
              isLoading={isTestingConnection}
              disabled={isSaving}
              mr={3}
            >
              Test Connection
            </Button>
            <Button
              type="submit"
              colorScheme="blue"
              isLoading={isSaving}
              disabled={isTestingConnection}
            >
              {isSaving ? <Spinner size="sm" /> : (isEditMode ? 'Save Changes' : 'Create')}
            </Button>
            <Button variant="ghost" onClick={onClose} ml={3} disabled={isSaving || isTestingConnection}>
              Cancel
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
};

export default DataSourceForm;
