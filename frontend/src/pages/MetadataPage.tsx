import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  Tag,
  Switch,
  Tooltip,
  useDisclosure // Import useDisclosure
} from '@chakra-ui/react';
import { ArrowBackIcon, RepeatIcon, ViewIcon } from '@chakra-ui/icons';
import dataSourceService, { DataSourceResponse } from '../services/dataSourceService';
import metadataService, { DataTableResponse, MetadataSyncResult } from '../services/metadataService';
import TablePreviewModal from '../components/Metadata/TablePreviewModal'; // Import the modal

const MetadataPage: React.FC = () => {
  const { datasourceId } = useParams<{ datasourceId: string }>();
  const navigate = useNavigate();
  const toast = useToast();

  const [dataSource, setDataSource] = useState<DataSourceResponse | null>(null);
  const [tables, setTables] = useState<DataTableResponse[]>([]);
  const [isLoadingDataSource, setIsLoadingDataSource] = useState(true);
  const [isLoadingTables, setIsLoadingTables] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedTableForPreview, setSelectedTableForPreview] = useState<DataTableResponse | null>(null);
  const { isOpen: isPreviewModalOpen, onOpen: onPreviewModalOpen, onClose: onPreviewModalClose } = useDisclosure();


  const fetchDataSourceDetails = useCallback(async () => {
    if (!datasourceId) return;
    setIsLoadingDataSource(true);
    try {
      const ds = await dataSourceService.getDataSourceById(datasourceId);
      setDataSource(ds);
    } catch (error: any) {
      toast({
        title: 'Error fetching data source details',
        description: error.message || 'Could not load data source information.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      // Optionally navigate back if data source can't be loaded
      // navigate('/datasources');
    } finally {
      setIsLoadingDataSource(false);
    }
  }, [datasourceId, toast]);

  const fetchTables = useCallback(async () => {
    if (!datasourceId) return;
    setIsLoadingTables(true);
    try {
      const tableData = await metadataService.getTablesForDataSource(datasourceId);
      setTables(tableData);
    } catch (error: any) {
      toast({
        title: 'Error fetching tables',
        description: error.message || 'Could not load tables for this data source.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoadingTables(false);
    }
  }, [datasourceId, toast]);

  useEffect(() => {
    fetchDataSourceDetails();
    fetchTables();
  }, [fetchDataSourceDetails, fetchTables]);

  const handleSyncMetadata = async () => {
    if (!datasourceId) return;
    setIsSyncing(true);
    try {
      const result: MetadataSyncResult = await metadataService.triggerMetadataSync(datasourceId);
      toast({
        title: 'Metadata Sync Initiated',
        description: result.message || `Sync completed. Discovered: ${result.tables_discovered}, Updated: ${result.tables_updated}, New: ${result.new_tables_added}. Status: ${result.status}`,
        status: result.status?.toLowerCase() === 'completed' || result.status?.toLowerCase() === 'success' ? 'success' : 'info',
        duration: 7000,
        isClosable: true,
      });
      fetchTables(); // Refresh tables list
    } catch (error: any) {
      toast({
        title: 'Metadata Sync Error',
        description: error.response?.data?.detail || error.message || 'Failed to sync metadata.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSyncing(false);
    }
  };

  // const [isTogglingTableId, setIsTogglingTableId] = useState<number | null>(null); // This was duplicated by mistake, removing older one.

  const [isTogglingTableId, setIsTogglingTableId] = useState<number | null>(null);

  const handleToggleActiveSync = async (table: DataTableResponse) => {
    if (!datasourceId) return;
    setIsTogglingTableId(table.id);
    try {
      const updatedTable = await metadataService.setTableActivation(table.id, !table.is_active_for_sync);
      setTables(prevTables =>
        prevTables.map(t => (t.id === updatedTable.id ? updatedTable : t))
      );
      toast({
        title: `Table '${table.name}' sync status updated`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error: any) {
      toast({
        title: 'Error updating table sync status',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsTogglingTableId(null);
    }
  };

  const handlePreviewData = (table: DataTableResponse) => {
    setSelectedTableForPreview(table);
    onPreviewModalOpen();
  };


  if (isLoadingDataSource || !dataSource) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="calc(100vh - 200px)">
        <Spinner size="xl" />
        <Text ml={4}>Loading data source information...</Text>
      </Box>
    );
  }

  return (
    <Box p={4}>
      <Flex mb={4} align="center">
        <IconButton
          icon={<ArrowBackIcon />}
          aria-label="Back to Data Sources"
          onClick={() => navigate('/datasources')}
          mr={4}
        />
        <Heading as="h2" size="lg">
          Metadata for: <Tag colorScheme="blue" size="lg">{dataSource.name}</Tag> (Type: {dataSource.type})
        </Heading>
        <Spacer />
        <Button
          leftIcon={<RepeatIcon />}
          colorScheme="teal"
          onClick={handleSyncMetadata}
          isLoading={isSyncing}
        >
          Sync Metadata
        </Button>
      </Flex>

      {isLoadingTables ? (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
          <Spinner size="lg" />
          <Text ml={3}>Loading tables...</Text>
        </Box>
      ) : tables.length === 0 ? (
        <Text mt={10} textAlign="center">No tables found for this data source. Try syncing metadata.</Text>
      ) : (
        <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
          <Table variant="simple">
            <Thead bg="gray.50">
              <Tr>
                <Th>Table Name</Th>
                <Th>Schema</Th>
                <Th isNumeric>Columns</Th>
                <Th>Active for Sync</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {tables.map((table) => (
                <Tr key={table.id}>
                  <Td>{table.name}</Td>
                  <Td>{table.schema_name || 'N/A'}</Td>
                  <Td isNumeric>{table.column_count ?? table.columns?.length ?? 'N/A'}</Td>
                  <Td>
                    <Tooltip label={table.is_active_for_sync ? 'Deactivate Sync' : 'Activate Sync'}>
                      <Switch
                        isChecked={table.is_active_for_sync}
                        onChange={() => handleToggleActiveSync(table)}
                        colorScheme="green"
                        isDisabled={isTogglingTableId === table.id}
                      />
                    </Tooltip>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <Button
                        leftIcon={<ViewIcon />}
                        size="sm"
                        variant="outline"
                        colorScheme="blue"
                        onClick={() => handlePreviewData(table)}
                      >
                        Preview
                      </Button>
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      {selectedTableForPreview && isPreviewModalOpen && (
        <TablePreviewModal
          isOpen={isPreviewModalOpen}
          onClose={() => {
            onPreviewModalClose();
            setSelectedTableForPreview(null); // Clear selection on close
          }}
          tableId={selectedTableForPreview.id}
          tableName={selectedTableForPreview.name}
        />
      )}
    </Box>
  );
};

export default MetadataPage;
