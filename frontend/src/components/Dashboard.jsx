import { useState, useEffect } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { getTopics } from '../api';
import TopicGraph from './TopicGraph';
import Collections from './Collections';

const COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#06b6d4'];

const PLATFORM_LABELS = {
  twitter: 'X / Twitter',
  linkedin: 'LinkedIn',
  reddit: 'Reddit',
  instagram: 'Instagram',
  chatgpt: 'ChatGPT',
  claude: 'Claude',
};

export default function Dashboard({ stats, onCategoryClick }) {
  const [topics, setTopics] = useState([]);

  // Load topics on mount
  useEffect(() => {
    loadTopics();
  }, []);

  const loadTopics = async () => {
    try {
      const data = await getTopics();
      setTopics(data.topics || []);
    } catch { /* ignore */ }
  };

  if (!stats || stats.total === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 text-center">
        <p className="text-gray-400 text-lg">Aucune donnée importée.</p>
        <p className="text-gray-400 text-sm mt-1">Commencez par importer vos fichiers d'export.</p>
      </div>
    );
  }

  const platformData = stats.by_platform.map((d) => ({
    name: PLATFORM_LABELS[d.platform] || d.platform,
    value: d.count,
  }));

  const timelineData = stats.timeline
    .filter((d) => d.month)
    .map((d) => ({ month: d.month, count: d.count }));

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPI label="Total items" value={stats.total} />
        <KPI label="Plateformes" value={stats.by_platform.length} />
        <KPI label="Types" value={stats.by_type.length} />
        <KPI label="Thématiques" value={topics.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform pie */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Par plateforme</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={platformData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {platformData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Timeline */}
        {timelineData.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Timeline</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Collections (Google Photos style) */}
      <Collections onCategoryClick={onCategoryClick} />

      {/* Topic Graph (force-directed) */}
      <TopicGraph onCategoryClick={onCategoryClick} />

      {/* Topics section — compact tag cloud only (collections + graph above cover the visual part) */}
      {topics.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Toutes les thématiques ({topics.length})</h3>
          <div className="flex flex-wrap gap-1.5">
            {topics.map((topic, i) => (
              <button
                key={topic.label}
                onClick={() => onCategoryClick?.(topic.label)}
                className="px-2.5 py-1 rounded-full text-xs font-medium hover:ring-1 transition-all cursor-pointer bg-gray-100 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600"
              >
                {topic.label} <span className="opacity-50">({topic.count})</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div className="text-2xl font-bold text-gray-900">{value.toLocaleString('fr-FR')}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
