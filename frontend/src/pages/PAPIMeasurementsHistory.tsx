import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { 
  Eye, 
  AlertCircle, 
  CheckCircle, 
  Clock, 
  Play,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Plus
} from 'lucide-react';
import api from '../services/api';
import { format } from 'date-fns';

interface MeasurementSession {
  id: string;
  airport_icao_code: string;
  runway_code: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  has_results: boolean;
}

interface SessionsResponse {
  sessions: MeasurementSession[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const PAPIMeasurementsHistory: React.FC = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<MeasurementSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchSessions = async (page: number = 1) => {
    try {
      setLoading(true);
      const response: SessionsResponse = await api.getPAPIMeasurementSessions(page, 20);
      setSessions(response.sessions);
      setCurrentPage(response.page);
      setTotalPages(response.total_pages);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError('Failed to load measurement sessions');
      // console.error('Error fetching sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchSessions(newPage);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" />Completed</Badge>;
      case 'processing':
        return <Badge variant="default" className="bg-blue-500"><Play className="w-3 h-3 mr-1" />Processing</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" />Pending</Badge>;
      case 'preview_ready':
        return <Badge variant="default" className="bg-orange-500"><Eye className="w-3 h-3 mr-1" />Preview Ready</Badge>;
      case 'error':
        return <Badge variant="destructive"><AlertCircle className="w-3 h-3 mr-1" />Error</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  const viewResults = (sessionId: string) => {
    // Navigate to results in same tab
    navigate(`/papi-measurements/results/${sessionId}`);
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        Loading measurement sessions...
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>PAPI Measurements</CardTitle>
              <p className="text-muted-foreground mt-1">
                View and manage all your PAPI light measurement sessions
              </p>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => navigate('/papi-measurements')} className="bg-blue-600 hover:bg-blue-700">
                <Plus className="w-4 h-4 mr-2" />
                Start New Measurement
              </Button>
              <Button onClick={() => fetchSessions(currentPage)} variant="outline">
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
              <div className="flex">
                <AlertCircle className="w-5 h-5 text-red-400 mr-2" />
                <span className="text-red-700">{error}</span>
              </div>
            </div>
          )}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Airport</TableHead>
                  <TableHead>Runway</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No measurement sessions found. Start a new measurement to see results here.
                    </TableCell>
                  </TableRow>
                ) : (
                  sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell className="font-medium">
                        {session.airport_icao_code}
                      </TableCell>
                      <TableCell>{session.runway_code}</TableCell>
                      <TableCell>{getStatusBadge(session.status)}</TableCell>
                      <TableCell>
                        {format(new Date(session.created_at), 'MMM dd, yyyy HH:mm')}
                      </TableCell>
                      <TableCell>{formatDuration(session.duration_seconds)}</TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          {session.has_results && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => viewResults(session.id)}
                              title="View Results"
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                          )}
                          {session.status === 'error' && session.error_message && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => alert(session.error_message)}
                              title="View Error Details"
                            >
                              <AlertCircle className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between space-x-2 py-4">
              <div className="text-sm text-muted-foreground">
                Showing {((currentPage - 1) * 20) + 1} to {Math.min(currentPage * 20, total)} of {total} sessions
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </Button>
                <span className="text-sm">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage >= totalPages}
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PAPIMeasurementsHistory;