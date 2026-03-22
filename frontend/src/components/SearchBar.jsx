import { useState } from 'react';
import { Search, Sparkles, Filter } from 'lucide-react';

export default function SearchBar({ onSearch, onSemanticSearch }) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('text'); // 'text' or 'semantic'
  const [platform, setPlatform] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    if (mode === 'semantic') {
      onSemanticSearch(query, platform || undefined);
    } else {
      onSearch(query, platform || undefined);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={mode === 'semantic' ? 'Recherche intelligente (ex: "projet sur le tricot")...' : 'Rechercher dans vos contenus...'}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-200 text-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>

        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600
                     focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">Toutes</option>
          <option value="twitter">X / Twitter</option>
          <option value="linkedin">LinkedIn</option>
          <option value="reddit">Reddit</option>
          <option value="instagram">Instagram</option>
          <option value="chatgpt">ChatGPT</option>
          <option value="claude">Claude</option>
        </select>

        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
          <button
            type="button"
            onClick={() => setMode('text')}
            className={`px-3 py-2 text-sm flex items-center gap-1.5 transition-colors ${
              mode === 'text' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-50'
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Texte
          </button>
          <button
            type="button"
            onClick={() => setMode('semantic')}
            className={`px-3 py-2 text-sm flex items-center gap-1.5 transition-colors ${
              mode === 'semantic' ? 'bg-purple-100 text-purple-700' : 'text-gray-500 hover:bg-gray-50'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            IA
          </button>
        </div>

        <button
          type="submit"
          className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium
                     hover:bg-indigo-700 transition-colors"
        >
          Chercher
        </button>
      </div>
    </form>
  );
}
