/**
 * Master API Client
 * Handles all communication with the master backend API
 */

const API_URL = process.env.NEXT_PUBLIC_MASTER_API_URL || 'http://localhost:8000';

class MasterAPIClient {
  private getHeaders(): HeadersInit {
    const token = typeof window !== 'undefined' ? localStorage.getItem('master_session_token') : null;
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': token }),
    };
  }

  // ============================================================================
  // Authentication
  // ============================================================================

  async login(email: string, password: string) {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await res.json();
    localStorage.setItem('master_session_token', data.session_token);
    localStorage.setItem('master_admin', JSON.stringify(data));
    return data;
  }

  async logout() {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        headers: this.getHeaders(),
      });
    } finally {
      localStorage.removeItem('master_session_token');
      localStorage.removeItem('master_admin');
    }
  }

  isAuthenticated(): boolean {
    if (typeof window === 'undefined') return false;
    return !!localStorage.getItem('master_session_token');
  }

  getAdmin() {
    if (typeof window === 'undefined') return null;
    const admin = localStorage.getItem('master_admin');
    return admin ? JSON.parse(admin) : null;
  }

  // ============================================================================
  // Companies
  // ============================================================================

  async getCompanies() {
    const res = await fetch(`${API_URL}/companies`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch companies');
    return res.json();
  }

  async getCompany(id: string) {
    const res = await fetch(`${API_URL}/companies/${id}`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch company');
    return res.json();
  }

  async createCompany(data: any) {
    const res = await fetch(`${API_URL}/companies`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to create company');
    }

    return res.json();
  }

  async updateCompany(id: string, data: any) {
    const res = await fetch(`${API_URL}/companies/${id}`, {
      method: 'PATCH',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error('Failed to update company');
    return res.json();
  }

  async deleteCompany(id: string) {
    const res = await fetch(`${API_URL}/companies/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to delete company');
    return res.json();
  }

  // ============================================================================
  // Schemas
  // ============================================================================

  async getSchemas(companyId: string) {
    const res = await fetch(`${API_URL}/schemas/${companyId}`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch schemas');
    return res.json();
  }

  async createSchema(data: any) {
    const res = await fetch(`${API_URL}/schemas`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to create schema');
    }

    return res.json();
  }

  async deleteSchema(id: number) {
    const res = await fetch(`${API_URL}/schemas/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to delete schema');
    return res.json();
  }

  // ============================================================================
  // Deployments
  // ============================================================================

  async getDeployment(companyId: string) {
    const res = await fetch(`${API_URL}/deployments/${companyId}`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch deployment');
    return res.json();
  }

  async createDeployment(data: any) {
    const res = await fetch(`${API_URL}/deployments`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to create deployment');
    }

    return res.json();
  }

  // ============================================================================
  // Team Members
  // ============================================================================

  async getTeamMembers(companyId: string) {
    const res = await fetch(`${API_URL}/team-members/${companyId}`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch team members');
    return res.json();
  }

  async createTeamMember(data: any) {
    const res = await fetch(`${API_URL}/team-members`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to create team member');
    }

    return res.json();
  }

  // ============================================================================
  // Stats
  // ============================================================================

  async getStats() {
    const res = await fetch(`${API_URL}/stats`, {
      headers: this.getHeaders(),
    });

    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  }

  // ============================================================================
  // Health
  // ============================================================================

  async healthCheck() {
    const res = await fetch(`${API_URL}/health`);
    return res.json();
  }
}

export const api = new MasterAPIClient();
