'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { FileCode, Plus, Trash2 } from 'lucide-react';

export default function SchemasPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [schemas, setSchemas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompany) {
      loadSchemas(selectedCompany);
    }
  }, [selectedCompany]);

  const loadCompanies = async () => {
    try {
      const data = await api.getCompanies();
      setCompanies(data.filter((c: any) => c.status === 'active'));
      if (data.length > 0) {
        setSelectedCompany(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSchemas = async (companyId: string) => {
    try {
      const data = await api.getSchemas(companyId);
      setSchemas(data);
    } catch (error) {
      console.error('Failed to load schemas:', error);
    }
  };

  const handleAddSchema = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

    try {
      await api.createSchema({
        company_id: selectedCompany,
        override_type: formData.get('override_type'),
        entity_type: formData.get('entity_type'),
        description: formData.get('description'),
      });

      setShowAddModal(false);
      loadSchemas(selectedCompany);
    } catch (error: any) {
      alert('Failed to add schema: ' + error.message);
    }
  };

  const handleDeleteSchema = async (schemaId: number) => {
    if (!confirm('Are you sure you want to delete this schema?')) return;

    try {
      await api.deleteSchema(schemaId);
      loadSchemas(selectedCompany);
    } catch (error: any) {
      alert('Failed to delete schema: ' + error.message);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  const selectedCompanyData = companies.find((c) => c.id === selectedCompany);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Custom Schemas</h1>
          <p className="text-gray-400">Manage entity types and relationships per company</p>
        </div>
        {selectedCompany && (
          <button
            onClick={() => setShowAddModal(true)}
            className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Add Schema</span>
          </button>
        )}
      </div>

      {/* Company Selector */}
      {companies.length > 0 && (
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Select Company
          </label>
          <select
            value={selectedCompany}
            onChange={(e) => setSelectedCompany(e.target.value)}
            className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          >
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name} ({company.slug})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Schemas List */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="p-6 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">
            {selectedCompanyData?.name || 'Select a company'}
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            {schemas.length} custom schema{schemas.length !== 1 ? 's' : ''}
          </p>
        </div>

        {schemas.length === 0 ? (
          <div className="p-12 text-center">
            <FileCode className="w-16 h-16 text-gray-700 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-400 mb-2">
              No custom schemas
            </h3>
            <p className="text-gray-500 mb-6">
              Add custom entity types or relationships for this company
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-colors"
            >
              Add First Schema
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {schemas.map((schema) => (
              <div
                key={schema.id}
                className="p-6 hover:bg-gray-800/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="px-3 py-1 bg-purple-600/20 text-purple-400 text-sm font-medium rounded-md">
                        {schema.override_type === 'entity' ? 'Entity' : 'Relation'}
                      </span>
                      <span className="text-xl font-mono font-semibold text-white">
                        {schema.entity_type || schema.relation_type}
                      </span>
                    </div>
                    {schema.description && (
                      <p className="text-sm text-gray-400">{schema.description}</p>
                    )}
                    <div className="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                      <span>Created by {schema.created_by}</span>
                      <span>•</span>
                      <span>{new Date(schema.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteSchema(schema.id)}
                    className="ml-4 p-2 text-red-400 hover:bg-red-900/20 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Schema Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-white mb-6">Add Custom Schema</h2>

            <form onSubmit={handleAddSchema} className="space-y-4">
              {/* Type */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Type
                </label>
                <select
                  name="override_type"
                  required
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="entity">Entity</option>
                  <option value="relation">Relation</option>
                </select>
              </div>

              {/* Entity/Relation Name */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Name (e.g., MACHINE, PRODUCT)
                </label>
                <input
                  type="text"
                  name="entity_type"
                  required
                  placeholder="MACHINE"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Description
                </label>
                <textarea
                  name="description"
                  rows={3}
                  placeholder="Describe this entity type..."
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Buttons */}
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 px-4 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all"
                >
                  Add Schema
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
