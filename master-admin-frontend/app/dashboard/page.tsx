'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Building2, Activity, Clock, TrendingUp } from 'lucide-react';

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Companies',
      value: stats?.total_companies || 0,
      icon: Building2,
      color: 'from-blue-500 to-cyan-500',
    },
    {
      title: 'Active',
      value: stats?.active_companies || 0,
      icon: Activity,
      color: 'from-green-500 to-emerald-500',
    },
    {
      title: 'Trial',
      value: stats?.trial_companies || 0,
      icon: Clock,
      color: 'from-yellow-500 to-orange-500',
    },
    {
      title: 'Provisioning',
      value: stats?.provisioning || 0,
      icon: TrendingUp,
      color: 'from-purple-500 to-pink-500',
    },
  ];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">Overview of all CORTEX deployments</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.title}
              className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors"
            >
              <div className="flex items-center justify-between mb-4">
                <div
                  className={`w-12 h-12 rounded-lg bg-gradient-to-r ${stat.color} flex items-center justify-center`}
                >
                  <Icon className="w-6 h-6 text-white" />
                </div>
              </div>
              <div>
                <p className="text-gray-400 text-sm mb-1">{stat.title}</p>
                <p className="text-3xl font-bold text-white">{stat.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="px-6 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all">
            Add New Company
          </button>
          <button className="px-6 py-4 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors">
            View All Companies
          </button>
          <button className="px-6 py-4 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors">
            Manage Schemas
          </button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="mt-8 bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Recent Activity</h2>
        <div className="text-gray-400 text-sm">
          <p>No recent activity</p>
        </div>
      </div>
    </div>
  );
}
