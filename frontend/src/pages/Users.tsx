import React, { useState, useEffect } from 'react';
import api from '../services/api';

interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  phone?: string;
  organization?: string;
  created_at: string;
  airports?: Airport[];
}

interface Airport {
  id: string;
  icao_code: string;
  name: string;
}

interface UserFormData {
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  password: string;
  role: string;
  phone: string;
  organization: string;
}

const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showAirportModal, setShowAirportModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [managingAirportsUser, setManagingAirportsUser] = useState<User | null>(null);
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    username: '',
    first_name: '',
    last_name: '',
    password: '',
    role: 'viewer',
    phone: '',
    organization: '',
  });

  const roles = [
    { value: 'super_admin', label: 'Super Admin' },
    { value: 'airport_admin', label: 'Airport Admin' },
    { value: 'maintenance_manager', label: 'Maintenance Manager' },
    { value: 'drone_operator', label: 'Drone Operator' },
    { value: 'viewer', label: 'Viewer' },
  ];

  useEffect(() => {
    fetchUsers();
    fetchAirports();
  }, [page, search, selectedRole]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const params: any = { page, page_size: 20 };
      if (search) params.search = search;
      if (selectedRole) params.role = selectedRole;

      const response = await api.getUsers(params);
      setUsers(response.users || []);
      setTotalPages(Math.ceil(response.total / 20));
    } catch (error: any) {
      console.error('Error fetching users:', error);
      alert(error.response?.data?.detail || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const fetchAirports = async () => {
    try {
      const response = await api.getAirports({ page_size: 100 });
      setAirports(response.airports || []);
    } catch (error) {
      console.error('Error fetching airports:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingUser) {
        const updateData = { ...formData };
        if (!formData.password) {
          delete (updateData as any).password;
        }
        await api.updateUser(editingUser.id, updateData);
        alert('User updated successfully');
      } else {
        if (!formData.password) {
          alert('Password is required for new users');
          return;
        }
        await api.createUser(formData);
        alert('User created successfully');
      }
      setShowModal(false);
      resetForm();
      fetchUsers();
    } catch (error: any) {
      console.error('Error saving user:', error);
      alert(error.response?.data?.detail || 'Failed to save user');
    }
  };

  const handleDelete = async () => {
    if (!deletingUser) return;
    try {
      await api.deleteUser(deletingUser.id);
      alert('User deleted successfully');
      setShowDeleteConfirm(false);
      setDeletingUser(null);
      fetchUsers();
    } catch (error: any) {
      console.error('Error deleting user:', error);
      alert(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleAssignAirport = async (airportId: string) => {
    if (!managingAirportsUser) return;
    try {
      await api.assignUserToAirport(managingAirportsUser.id, airportId);
      alert('Airport assigned successfully');
      // Refresh the user details to update the airport list
      await openAirportModal(managingAirportsUser.id);
    } catch (error: any) {
      console.error('Error assigning airport:', error);
      alert(error.response?.data?.detail || 'Failed to assign airport');
    }
  };

  const handleUnassignAirport = async (airportId: string) => {
    if (!managingAirportsUser) return;
    try {
      await api.unassignUserFromAirport(managingAirportsUser.id, airportId);
      alert('Airport unassigned successfully');
      // Refresh the user details to update the airport list
      await openAirportModal(managingAirportsUser.id);
    } catch (error: any) {
      console.error('Error unassigning airport:', error);
      alert(error.response?.data?.detail || 'Failed to unassign airport');
    }
  };

  const openAirportModal = async (userId: string) => {
    try {
      // Fetch user details with airports
      const userDetails = await api.getUser(userId);
      setManagingAirportsUser(userDetails);
      setShowAirportModal(true);
    } catch (error: any) {
      console.error('Error fetching user details:', error);
      alert(error.response?.data?.detail || 'Failed to fetch user details');
    }
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      password: '',
      role: user.role,
      phone: user.phone || '',
      organization: user.organization || '',
    });
    setShowModal(true);
  };

  const openCreateModal = () => {
    setEditingUser(null);
    resetForm();
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      email: '',
      username: '',
      first_name: '',
      last_name: '',
      password: '',
      role: 'viewer',
      phone: '',
      organization: '',
    });
  };

  const getRoleBadgeClass = (role: string) => {
    const classes: Record<string, string> = {
      super_admin: 'bg-red-100 text-red-800',
      airport_admin: 'bg-purple-100 text-purple-800',
      maintenance_manager: 'bg-blue-100 text-blue-800',
      drone_operator: 'bg-green-100 text-green-800',
      viewer: 'bg-gray-100 text-gray-800',
    };
    return classes[role] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-4">Users Management</h1>

        {/* Filters and Actions */}
        <div className="bg-white p-4 rounded-lg shadow mb-4">
          <div className="flex flex-wrap gap-4">
            <input
              type="text"
              placeholder="Search users..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="px-4 py-2 border rounded-md flex-1 min-w-[200px]"
            />
            <select
              value={selectedRole}
              onChange={(e) => { setSelectedRole(e.target.value); setPage(1); }}
              className="px-4 py-2 border rounded-md"
            >
              <option value="">All Roles</option>
              {roles.map((role) => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </select>
            <button
              onClick={openCreateModal}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              + Create User
            </button>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Username
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Organization
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-4 text-center text-gray-500">
                      Loading users...
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-4 text-center text-gray-500">
                      No users found
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {user.first_name} {user.last_name}
                          </div>
                          <div className="text-sm text-gray-500">{user.email}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {user.username}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getRoleBadgeClass(user.role)}`}>
                          {roles.find(r => r.value === user.role)?.label || user.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {user.organization || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => openEditModal(user)}
                          className="text-blue-600 hover:text-blue-900 mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => openAirportModal(user.id)}
                          className="text-green-600 hover:text-green-900 mr-3"
                        >
                          Airports
                        </button>
                        <button
                          onClick={() => {
                            setDeletingUser(user);
                            setShowDeleteConfirm(true);
                          }}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 border rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 border rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">
              {editingUser ? 'Edit User' : 'Create New User'}
            </h2>
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Last Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email *
                  </label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password {!editingUser && '*'}
                  </label>
                  <input
                    type="password"
                    required={!editingUser}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder={editingUser ? 'Leave empty to keep current' : ''}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role *
                  </label>
                  <select
                    required
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    {roles.map((role) => (
                      <option key={role.value} value={role.value}>{role.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone
                  </label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Organization
                  </label>
                  <input
                    type="text"
                    value={formData.organization}
                    onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  className="px-4 py-2 border rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  {editingUser ? 'Update User' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && deletingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4">Confirm Delete</h2>
            <p className="mb-6">
              Are you sure you want to delete user <strong>{deletingUser.first_name} {deletingUser.last_name}</strong>?
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowDeleteConfirm(false); setDeletingUser(null); }}
                className="px-4 py-2 border rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Delete User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Airport Management Modal */}
      {showAirportModal && managingAirportsUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">
              Manage Airports for {managingAirportsUser.first_name} {managingAirportsUser.last_name}
            </h2>
            <div className="space-y-2">
              {airports.map((airport) => {
                const isAssigned = managingAirportsUser?.airports?.some(a => a.id === airport.id) || false;
                return (
                  <div key={airport.id} className="flex items-center justify-between p-3 border rounded-md">
                    <div>
                      <div className="font-medium">{airport.name}</div>
                      <div className="text-sm text-gray-500">{airport.icao_code}</div>
                    </div>
                    <button
                      onClick={() => isAssigned ? handleUnassignAirport(airport.id) : handleAssignAirport(airport.id)}
                      className={`px-4 py-2 rounded-md ${isAssigned ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} text-white`}
                    >
                      {isAssigned ? 'Unassign' : 'Assign'}
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => { setShowAirportModal(false); setManagingAirportsUser(null); }}
                className="px-4 py-2 border rounded-md text-gray-700 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Users;
