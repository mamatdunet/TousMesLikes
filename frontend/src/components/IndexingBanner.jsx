import { Database, CheckCircle } from 'lucide-react';

export default function IndexingBanner({ indexing }) {
  if (!indexing) return null;

  const percent = indexing.total > 0 ? Math.round((indexing.done / indexing.total) * 100) : 0;

  return (
    <div className={`border-b ${indexing.running ? 'bg-indigo-50 border-indigo-200' : 'bg-green-50 border-green-200'}`}>
      <div className="max-w-6xl mx-auto px-4 py-2">
        <div className="flex items-center gap-3">
          {indexing.running ? (
            <Database className="w-4 h-4 text-indigo-600 animate-pulse shrink-0" />
          ) : (
            <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className={indexing.running ? 'text-indigo-700' : 'text-green-700'}>
                {indexing.running
                  ? `Indexation IA en cours (${indexing.platform})...`
                  : 'Indexation terminée'}
              </span>
              <span className={`text-xs ${indexing.running ? 'text-indigo-500' : 'text-green-500'}`}>
                {indexing.done} / {indexing.total} — {percent}%
              </span>
            </div>
            <div className="w-full bg-white/60 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all duration-500 ${indexing.running ? 'bg-indigo-500' : 'bg-green-500'}`}
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
          {indexing.error && (
            <span className="text-xs text-red-500 shrink-0">Erreur : {indexing.error}</span>
          )}
        </div>
      </div>
    </div>
  );
}
