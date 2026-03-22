import { useState, useEffect } from 'react';
import { CircleDot, AlertTriangle } from 'lucide-react';
import { getOllamaStatus } from '../api';

export default function OllamaStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    getOllamaStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status) return null;

  if (!status.available) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-gray-400" title="Ollama non détecté">
        <CircleDot className="w-3 h-3" />
        <span>Ollama off</span>
      </div>
    );
  }

  const allGood = status.has_embed && status.has_chat;

  return (
    <div
      className={`flex items-center gap-1.5 text-xs ${allGood ? 'text-green-600' : 'text-amber-500'}`}
      title={`Modèles: ${status.models.join(', ') || 'aucun'}`}
    >
      {allGood ? (
        <CircleDot className="w-3 h-3" />
      ) : (
        <AlertTriangle className="w-3 h-3" />
      )}
      <span>
        Ollama
        {!status.has_embed && <span className="text-amber-400 ml-1">(embed manquant)</span>}
        {!status.has_chat && <span className="text-amber-400 ml-1">(chat manquant)</span>}
      </span>
    </div>
  );
}
