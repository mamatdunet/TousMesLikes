import { useEffect, useState } from 'react';
import { getCollections } from '../api';

const PLATFORM_ICONS = {
  twitter: '𝕏',
  reddit: '🤖',
  instagram: '📷',
  facebook: 'f',
  linkedin: 'in',
  youtube: '▶',
  chatgpt: '🤖',
  claude: '🧠',
};

export default function Collections({ onCategoryClick }) {
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCollections(16)
      .then((data) => setCollections(data.collections || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-12 text-gray-400">Chargement des collections...</div>;
  if (!collections.length) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-800 mb-3">Vos thématiques</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {collections.map((col) => (
          <button
            key={col.category}
            onClick={() => onCategoryClick && onCategoryClick(col.category)}
            className="group relative bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-all text-left"
          >
            {/* Cover image or gradient */}
            <div className="h-28 relative overflow-hidden">
              {col.cover ? (
                <img
                  src={col.cover}
                  alt=""
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-indigo-100 to-indigo-300 flex items-center justify-center">
                  <span className="text-3xl opacity-30">{col.category.slice(0, 2)}</span>
                </div>
              )}
              {/* Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
              <div className="absolute bottom-2 left-2 right-2">
                <h4 className="text-white text-sm font-semibold leading-tight drop-shadow-sm truncate">
                  {col.category}
                </h4>
              </div>
            </div>

            {/* Footer */}
            <div className="px-2.5 py-2 flex items-center justify-between">
              <span className="text-xs text-gray-500">{col.count} items</span>
              <div className="flex gap-0.5">
                {col.platforms.map((p) => (
                  <span key={p} className="text-[10px] opacity-50" title={p}>
                    {PLATFORM_ICONS[p] || p[0]}
                  </span>
                ))}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
