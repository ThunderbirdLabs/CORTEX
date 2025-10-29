'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { FileText, Save, X } from 'lucide-react';

export default function PromptsPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [prompts, setPrompts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPrompt, setEditingPrompt] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompany) {
      loadPrompts(selectedCompany);
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

  const loadPrompts = async (companyId: string) => {
    try {
      const data = await api.getPrompts(companyId);
      setPrompts(data);
    } catch (error) {
      console.error('Failed to load prompts:', error);
    }
  };

  const handleEditPrompt = (prompt: any) => {
    setEditingPrompt({
      ...prompt,
      prompt_template: prompt.prompt_template,
    });
  };

  const handleSavePrompt = async () => {
    if (!editingPrompt) return;

    setSaving(true);
    try {
      await api.updatePrompt(
        selectedCompany,
        editingPrompt.prompt_key,
        {
          prompt_template: editingPrompt.prompt_template,
          prompt_name: editingPrompt.prompt_name,
          prompt_description: editingPrompt.prompt_description,
        }
      );

      setEditingPrompt(null);
      loadPrompts(selectedCompany);
      alert('Prompt updated successfully! Restart backend for changes to take effect.');
    } catch (error: any) {
      alert('Failed to update prompt: ' + error.message);
    } finally {
      setSaving(false);
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

  const getPromptTypeLabel = (promptKey: string) => {
    switch (promptKey) {
      case 'ceo_assistant':
        return 'CEO Assistant';
      case 'entity_extraction':
        return 'Entity Extraction';
      case 'entity_deduplication':
        return 'Entity Deduplication';
      case 'vision_ocr_business_check':
        return 'Vision OCR Business Check';
      case 'vision_ocr_extract':
        return 'Vision OCR Extract';
      case 'email_classifier':
        return 'Email Classifier';
      default:
        return promptKey;
    }
  };

  const getPromptColor = (promptKey: string) => {
    switch (promptKey) {
      case 'ceo_assistant':
        return 'bg-blue-600/20 text-blue-400';
      case 'entity_extraction':
        return 'bg-green-600/20 text-green-400';
      case 'entity_deduplication':
        return 'bg-yellow-600/20 text-yellow-400';
      case 'vision_ocr_business_check':
        return 'bg-purple-600/20 text-purple-400';
      case 'vision_ocr_extract':
        return 'bg-pink-600/20 text-pink-400';
      case 'email_classifier':
        return 'bg-orange-600/20 text-orange-400';
      default:
        return 'bg-gray-600/20 text-gray-400';
    }
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Prompt Management</h1>
          <p className="text-gray-400">Edit AI prompts used across the system</p>
        </div>
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

      {/* Prompts List */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="p-6 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">
            {selectedCompanyData?.name || 'Select a company'}
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            {prompts.length} prompt{prompts.length !== 1 ? 's' : ''}
          </p>
        </div>

        {prompts.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="w-16 h-16 text-gray-700 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-400 mb-2">
              No prompts found
            </h3>
            <p className="text-gray-500">
              Run the seed script to populate default prompts
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {prompts.map((prompt) => (
              <div
                key={prompt.id}
                className="p-6 hover:bg-gray-800/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className={`px-3 py-1 text-sm font-medium rounded-md ${getPromptColor(prompt.prompt_key)}`}>
                        {getPromptTypeLabel(prompt.prompt_key)}
                      </span>
                      <span className="text-xs text-gray-500">
                        v{prompt.version || 1}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-1">
                      {prompt.prompt_name}
                    </h3>
                    {prompt.prompt_description && (
                      <p className="text-sm text-gray-400 mb-3">{prompt.prompt_description}</p>
                    )}
                    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 font-mono text-sm text-gray-300 max-h-32 overflow-y-auto">
                      {prompt.prompt_template.substring(0, 200)}
                      {prompt.prompt_template.length > 200 && '...'}
                    </div>
                    <div className="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                      <span>Updated {new Date(prompt.updated_at || prompt.created_at).toLocaleDateString()}</span>
                      {prompt.created_by && (
                        <>
                          <span>•</span>
                          <span>by {prompt.created_by}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleEditPrompt(prompt)}
                    className="ml-4 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-colors"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit Prompt Modal */}
      {editingPrompt && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-white">Edit Prompt</h2>
                <p className="text-sm text-gray-400 mt-1">
                  {getPromptTypeLabel(editingPrompt.prompt_key)} (v{editingPrompt.version || 1})
                </p>
              </div>
              <button
                onClick={() => setEditingPrompt(null)}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Prompt Name */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Prompt Name
                </label>
                <input
                  type="text"
                  value={editingPrompt.prompt_name}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, prompt_name: e.target.value })
                  }
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Prompt Description */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Description
                </label>
                <input
                  type="text"
                  value={editingPrompt.prompt_description || ''}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, prompt_description: e.target.value })
                  }
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Prompt Template */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Prompt Template
                </label>
                <textarea
                  value={editingPrompt.prompt_template}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, prompt_template: e.target.value })
                  }
                  rows={20}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Buttons */}
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setEditingPrompt(null)}
                  className="flex-1 px-4 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors"
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSavePrompt}
                  disabled={saving}
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all flex items-center justify-center space-x-2"
                >
                  <Save className="w-5 h-5" />
                  <span>{saving ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
