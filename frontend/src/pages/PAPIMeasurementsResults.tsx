import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { ArrowLeft } from 'lucide-react';
import MeasurementDataDisplay from '../components/MeasurementDataDisplay';

const PAPIMeasurementsResults: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  if (!sessionId) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center">
          <div className="text-red-600 mb-4">Invalid session ID</div>
          <Button onClick={() => navigate('/papi-measurements/history')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to History
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Button 
            variant="outline" 
            onClick={() => navigate('/papi-measurements/history')}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to History
          </Button>
          <h1 className="text-2xl font-bold">PAPI Measurement Report</h1>
        </div>
      </div>

      {/* Complete Measurement Report with all charts, videos, and analysis */}
      <MeasurementDataDisplay sessionId={sessionId} />
    </div>
  );
};

export default PAPIMeasurementsResults;