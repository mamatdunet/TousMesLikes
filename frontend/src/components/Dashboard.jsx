import { useState, useEffect } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Treemap,
} from 'recharts';
import { getTopics } from '../api';
import TopicGraph from './TopicGraph';
import Collections from './Collections';

const COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#06b6d4'];
const TREEMAP_COLORS = [
  '#6366f1', '#818cf8', '#a5b4fc', '#8b5cf6', '#a78bfa', '#c4b5fd',
  '#a855f7', '#c084fc', '#d8b4fe', '#d946ef', '#e879f9', '#f0abfc',
  '#ec4899', '#f472b6', '#f9a8d4', '#f43f5e', '#fb7185', '#fda4af',
];

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

  // Treemap data for topics
  const treemapData = topics.slice(0, 20).map((t, i) => ({
    name: t.label,
    size: t.count,
    fill: TREEMAP_COLORS[i % TREEMAP_COLORS.length],
  }));

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

      {/* Topics section */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Thématiques principales</h3>

        {topics.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">
            Aucune thématique détectée pour le moment.
          </p>
        ) : (
          <div className="space-y-4">
            {/* Treemap visualization */}
            {treemapData.length > 0 && (
              <ResponsiveContainer width="100%" height={300}>
                <Treemap
                  data={treemapData}
                  dataKey="size"
                  nameKey="name"
                  stroke="#fff"
                  content={<CustomTreemapContent onClick={onCategoryClick} />}
                />
              </ResponsiveContainer>
            )}

            {/* Topic list as ranked tags */}
            <div className="flex flex-wrap gap-2 pt-2">
              {topics.map((topic, i) => (
                <button
                  key={topic.label}
                  onClick={() => onCategoryClick?.(topic.label)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium
                             hover:ring-2 hover:ring-offset-1 transition-all cursor-pointer"
                  style={{
                    backgroundColor: `${TREEMAP_COLORS[i % TREEMAP_COLORS.length]}15`,
                    color: TREEMAP_COLORS[i % TREEMAP_COLORS.length],
                    '--tw-ring-color': TREEMAP_COLORS[i % TREEMAP_COLORS.length],
                  }}
                >
                  <span className="font-semibold text-xs opacity-60">#{i + 1}</span>
                  {topic.label}
                  <span className="text-xs opacity-60">({topic.count})</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CustomTreemapContent({ x, y, width, height, name, fill, onClick }) {
  if (width < 40 || height < 30) return null;
  return (
    <g style={{ cursor: 'pointer' }} onClick={() => onClick?.(name)}>
      <rect x={x} y={y} width={width} height={height} fill={fill} rx={4} stroke="#fff" strokeWidth={2} />
      <foreignObject x={x + 4} y={y + 4} width={width - 8} height={height - 8}>
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          style={{
            color: '#fff',
            fontSize: width < 80 ? '10px' : '12px',
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            textShadow: '0 1px 2px rgba(0,0,0,0.3)',
          }}
        >
          {name}
        </div>
      </foreignObject>
    </g>
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
