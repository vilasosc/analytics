import React, { useEffect, useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Alert,
  AlertIcon,
  Box,
  Tag,
  useToast
} from '@chakra-ui/react';
import metadataService, { TablePreviewResponse, TablePreviewDataRow } from '../../services/metadataService';

interface TablePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  tableId: number | string;
  tableName: string;
}

const TablePreviewModal: React.FC<TablePreviewModalProps> = ({ isOpen, onClose, tableId, tableName }) => {
  const [previewData, setPreviewData] = useState<TablePreviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (isOpen && tableId) {
      setIsLoading(true);
      setError(null);
      setPreviewData(null); // Reset previous data

      metadataService.getTablePreview(tableId)
        .then(data => {
          setPreviewData(data);
        })
        .catch(err => {
          const errorMessage = err.response?.data?.detail || err.message || `Failed to fetch preview for table ${tableName}.`;
          setError(errorMessage);
          toast({
            title: 'Error fetching preview data',
            description: errorMessage,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen, tableId, tableName, toast]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="4xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          Previewing: <Tag colorScheme="cyan" size="lg" ml={2}>{tableName}</Tag>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {isLoading && (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
              <Spinner size="xl" />
            </Box>
          )}
          {error && !isLoading && (
            <Alert status="error">
              <AlertIcon />
              <Text>{error}</Text>
            </Alert>
          )}
          {previewData && !isLoading && !error && (
            <>
              <Text fontSize="sm" mb={2}>
                Showing <strong>{previewData.row_count_preview}</strong> of <strong>{previewData.row_count_total}</strong> total rows.
                {previewData.is_preview_limited && " (Preview is limited)"}
              </Text>
              {previewData.rows.length === 0 ? (
                <Text mt={4} textAlign="center">No data to display in the preview.</Text>
              ) : (
                <Box overflowX="auto">
                  <Table variant="simple" size="sm">
                    <Thead bg="gray.100">
                      <Tr>
                        {previewData.columns.map((colName) => (
                          <Th key={colName}>{colName}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {previewData.rows.map((row: TablePreviewDataRow, rowIndex: number) => (
                        <Tr key={rowIndex}>
                          {previewData.columns.map((colName) => (
                            <Td key={`${rowIndex}-${colName}`}>{String(row[colName])}</Td>
                          ))}
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>
              )}
            </>
          )}
        </ModalBody>
        <ModalFooter>
          {/* <Button onClick={onClose}>Close</Button> */}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default TablePreviewModal;
