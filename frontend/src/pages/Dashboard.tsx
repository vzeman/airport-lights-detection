import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar } from '../components/ui/avatar';
import {
  Plane,
  Users,
  ClipboardList,
  AlertTriangle,
  CheckCircle,
  Clock,
  Map as MapIcon,
  Loader2,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

interface DashboardStats {
  totalAirports: number;
  activeAirports: number;
  totalUsers: number;
  pendingTasks: number;
  completedTasks: number;
  upcomingInspections: number;
}

interface Airport {
  id: string;
  icao_code: string;
  name: string;
  city?: string;
  country: string;
  runway_count: number;
  is_active: boolean;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user, isSuperAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    totalAirports: 0,
    activeAirports: 0,
    totalUsers: 0,
    pendingTasks: 0,
    completedTasks: 0,
    upcomingInspections: 0,
  });
  const [airports, setAirports] = useState<Airport[]>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      // Fetch airports
      const airportsResponse = await api.getAirports({ page_size: 10 });
      setAirports(airportsResponse.airports);
      
      // Calculate stats (in a real app, this would come from a dedicated endpoint)
      setStats({
        totalAirports: airportsResponse.total,
        activeAirports: airportsResponse.airports.filter((a: Airport) => a.is_active).length,
        totalUsers: 0, // Would fetch from users endpoint
        pendingTasks: 5, // Mock data
        completedTasks: 12, // Mock data
        upcomingInspections: 3, // Mock data
      });
    } catch (error) {
      // console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const StatCard = ({ title, value, icon, bgColor }: any) => (
    <Card>
      <CardContent className="flex items-center justify-between p-6">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
        <div className={`h-12 w-12 rounded-full flex items-center justify-center ${bgColor}`}>
          {icon}
        </div>
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Welcome back, {user?.first_name}!</h1>
        <p className="text-muted-foreground mt-2">
          Here's an overview of your airport management system
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Airports"
          value={stats.totalAirports}
          icon={<Plane className="h-4 w-4 text-white" />}
          bgColor="bg-blue-500"
        />
        <StatCard
          title="Active Airports"
          value={stats.activeAirports}
          icon={<CheckCircle className="h-4 w-4 text-white" />}
          bgColor="bg-green-500"
        />
        <StatCard
          title="Pending Tasks"
          value={stats.pendingTasks}
          icon={<ClipboardList className="h-4 w-4 text-white" />}
          bgColor="bg-yellow-500"
        />
        <StatCard
          title="Upcoming Inspections"
          value={stats.upcomingInspections}
          icon={<Clock className="h-4 w-4 text-white" />}
          bgColor="bg-purple-500"
        />
      </div>

      {/* Main Content */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Your Airports */}
        <div className="md:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Your Airports</CardTitle>
                <Button variant="outline" size="sm" onClick={() => navigate('/airports')}>
                  View All
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                {airports.slice(0, 6).map((airport) => (
                  <Card key={airport.id} className="border">
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h3 className="font-semibold">{airport.icao_code}</h3>
                          <p className="text-sm text-muted-foreground">{airport.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {airport.city && `${airport.city}, `}{airport.country}
                          </p>
                        </div>
                        <Badge variant={airport.is_active ? 'success' : 'secondary'}>
                          {airport.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mb-3">
                        {airport.runway_count} runway{airport.runway_count !== 1 ? 's' : ''}
                      </p>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/airports/${airport.id}`)}
                        >
                          View Details
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/airports/${airport.id}/map`)}
                        >
                          <MapIcon className="mr-1 h-3 w-3" />
                          Map
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              {airports.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-muted-foreground mb-4">No airports assigned yet</p>
                  {(isSuperAdmin || user?.role === 'airport_admin') && (
                    <Button onClick={() => navigate('/airports')}>
                      Add Airport
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity & Quick Actions */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center space-x-3">
                  <Avatar className="h-8 w-8">
                    <div className="h-8 w-8 bg-green-500 rounded-full flex items-center justify-center">
                      <CheckCircle className="h-4 w-4 text-white" />
                    </div>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">Inspection Completed</p>
                    <p className="text-xs text-muted-foreground">KJFK - Runway 31L - 2 hours ago</p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <Avatar className="h-8 w-8">
                    <div className="h-8 w-8 bg-yellow-500 rounded-full flex items-center justify-center">
                      <AlertTriangle className="h-4 w-4 text-white" />
                    </div>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">Maintenance Required</p>
                    <p className="text-xs text-muted-foreground">EGLL - PAPI Lights - 5 hours ago</p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <Avatar className="h-8 w-8">
                    <div className="h-8 w-8 bg-blue-500 rounded-full flex items-center justify-center">
                      <Clock className="h-4 w-4 text-white" />
                    </div>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">Task Scheduled</p>
                    <p className="text-xs text-muted-foreground">LFPG - Monthly Survey - Tomorrow</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Button
                  className="w-full justify-start"
                  variant="outline"
                  onClick={() => navigate('/tasks')}
                >
                  <ClipboardList className="mr-2 h-4 w-4" />
                  Create Task
                </Button>
                <Button
                  className="w-full justify-start"
                  variant="outline"
                  onClick={() => navigate('/airports')}
                >
                  <Plane className="mr-2 h-4 w-4" />
                  Manage Airports
                </Button>
                {isSuperAdmin && (
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => navigate('/users')}
                  >
                    <Users className="mr-2 h-4 w-4" />
                    Manage Users
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;