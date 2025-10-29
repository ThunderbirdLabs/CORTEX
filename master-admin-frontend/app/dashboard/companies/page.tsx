'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Building2, ExternalLink, Circle } from 'lucide-react';

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    try {
      const data = await api.getCompanies();
      setCompanies(data);
    } catch (error) {
      console.error('Failed to load companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-400';
      case 'trial':
        return 'text-yellow-400';
      case 'provisioning':
        return 'text-blue-400';
      case 'suspended':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-gray-400">Loading companies...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Companies</h1>
          <p className="text-gray-400">Manage all CORTEX deployments</p>
        </div>
        <button className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all">
          + Add Company
        </button>
      </div>

      {/* Companies Grid */}
      {companies.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
          <Building2 className="w-16 h-16 text-gray-700 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400 mb-2">No companies yet</h3>
          <p className="text-gray-500 mb-6">Get started by adding your first company</p>
          <button className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-colors">
            Add First Company
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {companies.map((company) => (
            <div
              key={company.id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-all"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">
                    {company.name}
                  </h3>
                  <p className="text-sm text-gray-400">@{company.slug}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <Circle className={`w-3 h-3 ${getStatusColor(company.status)} fill-current`} />
                  <span className={`text-sm ${getStatusColor(company.status)} capitalize`}>
                    {company.status}
                  </span>
                </div>
              </div>

              {/* Details */}
              <div className="space-y-2 mb-4">
                {company.company_location && (
                  <p className="text-sm text-gray-400">
                    <span className="text-gray-500">Location:</span> {company.company_location}
                  </p>
                )}
                {company.plan && (
                  <p className="text-sm text-gray-400">
                    <span className="text-gray-500">Plan:</span>{' '}
                    <span className="capitalize">{company.plan}</span>
                  </p>
                )}
                {company.industries_served && company.industries_served.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {company.industries_served.map((industry: string, i: number) => (
                      <span
                        key={i}
                        className="px-2 py-1 bg-gray-800 text-gray-300 text-xs rounded-md"
                      >
                        {industry}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Links */}
              <div className="flex items-center space-x-4 pt-4 border-t border-gray-800">
                {company.frontend_url && (
                  <a
                    href={company.frontend_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-1 text-sm text-purple-400 hover:text-purple-300"
                  >
                    <span>Frontend</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {company.backend_url && (
                  <a
                    href={company.backend_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-1 text-sm text-purple-400 hover:text-purple-300"
                  >
                    <span>Backend</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              {/* Actions */}
              <div className="flex space-x-2 mt-4">
                <button className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors">
                  View Details
                </button>
                <button className="flex-1 px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 text-sm font-medium rounded-lg transition-colors">
                  Edit Schemas
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
