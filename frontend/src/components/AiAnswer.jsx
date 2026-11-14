import { useState } from 'react';
import { X, ChevronDown, ChevronUp } from 'lucide-react';
import { ItemCard } from './ItemList';

export default function AiAnswer({ answer, onClose }) {
  const [showOthers, setShowOthers] = useState(false);
  const sources = answer.sources || [];
  const cited = sources.filter((s) => s.cited);
  // When the answer cites nothing, show every source it was given
  const main = cited.length > 0 ? cited : sources;
  const others = cited.length > 0 ? sources.filter((s) => !s.cited) : [];

  return (
    <div className="mb-4 bg-purple-50 border border-purple-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-purple-600 text-sm font-semibold">Réponse IA</span>
        <button onClick={onClose} className="ml-auto text-purple-400 hover:text-purple-600">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <p className="text-sm text-gray-700 whitespace-pre-line">{answer.text}</p>

      {main.length > 0 && (
        <div className="mt-4 space-y-3">
          <p className="text-xs font-semibold text-purple-600">
            {cited.length > 0 ? 'Sources citées' : 'Contenus consultés'}
          </p>
          {main.map((item) => <ItemCard key={item.id} item={item} />)}
        </div>
      )}

      {others.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowOthers(!showOthers)}
            className="inline-flex items-center gap-1 text-xs font-medium text-purple-600 hover:text-purple-800"
          >
            {showOthers ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            Autres contenus consultés ({others.length})
          </button>
          {showOthers && (
            <div className="mt-3 space-y-3">
              {others.map((item) => <ItemCard key={item.id} item={item} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
