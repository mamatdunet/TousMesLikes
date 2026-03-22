import { useState, useRef, useEffect, useCallback } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, X } from 'lucide-react';

function Linkify({ children }) {
  if (typeof children !== 'string') return children;
  const parts = children.split(/(https?:\/\/[^\s<>"')\]]+)/g);
  if (parts.length === 1) return children;
  return parts.map((part, i) =>
    part.match(/^https?:\/\//) ? (
      <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800 underline break-all">
        {part.length > 60 ? part.slice(0, 57) + '...' : part}
      </a>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

const PLATFORM_COLORS = {
  twitter: 'bg-sky-100 text-sky-700',
  linkedin: 'bg-blue-100 text-blue-700',
  reddit: 'bg-orange-100 text-orange-700',
  instagram: 'bg-pink-100 text-pink-700',
  facebook: 'bg-blue-100 text-blue-700',
  youtube: 'bg-red-100 text-red-700',
  chatgpt: 'bg-emerald-100 text-emerald-700',
  claude: 'bg-amber-100 text-amber-700',
};

function Lightbox({ src, onClose }) {
  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-white/20 hover:bg-white/40 text-white transition-colors"
      >
        <X className="w-8 h-8" />
      </button>
      <img
        src={src}
        alt=""
        className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

function MediaGallery({ media }) {
  const [expanded, setExpanded] = useState(false);
  const [lightboxSrc, setLightboxSrc] = useState(null);
  if (!media || media.length === 0) return null;

  const shown = expanded ? media : media.slice(0, 4);

  return (
    <div className="mt-3">
      {lightboxSrc && <Lightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />}
      <div className={`grid gap-2 ${
        shown.length === 1 ? 'grid-cols-1' :
        shown.length === 2 ? 'grid-cols-2' :
        'grid-cols-2 md:grid-cols-3'
      }`}>
        {shown.map((m, i) => (
          <div key={i} className="relative rounded-lg overflow-hidden bg-gray-100">
            {m.type === 'image' ? (
              <button onClick={() => setLightboxSrc(m.url)} className="w-full">
                <img
                  src={m.url}
                  alt=""
                  loading="lazy"
                  className="w-full h-auto max-h-[500px] object-contain hover:opacity-90 transition-opacity cursor-zoom-in"
                />
              </button>
            ) : m.type === 'video' ? (
              <video
                src={m.url}
                controls
                preload="metadata"
                className="w-full h-auto max-h-[500px] object-contain bg-black"
              />
            ) : null}
          </div>
        ))}
      </div>
      {!expanded && media.length > 4 && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-1.5 text-xs text-indigo-600 hover:text-indigo-800"
        >
          +{media.length - 4} média{media.length - 4 > 1 ? 's' : ''}
        </button>
      )}
    </div>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function ItemCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  const contentRef = useRef(null);
  const [isClamped, setIsClamped] = useState(false);

  // Avoid showing content if it's the same as title (or title is a truncated version of content)
  const contentIsDuplicate = !item.content || !item.title ? false
    : item.content === item.title || item.content.startsWith(item.title) || item.title.startsWith(item.content);
  const hasContent = item.content && !contentIsDuplicate;

  useEffect(() => {
    if (contentRef.current) {
      setIsClamped(contentRef.current.scrollHeight > contentRef.current.clientHeight + 2);
    }
  }, [item.content]);

  const formattedDate = formatDate(item.created_at);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PLATFORM_COLORS[item.platform] || 'bg-gray-100 text-gray-600'}`}>
              {item.platform}
            </span>
            <span className="text-xs text-gray-400">{item.type}</span>
            {formattedDate && (
              <span className="text-xs text-gray-400">{formattedDate}</span>
            )}
            {item.relevance_score != null && (
              <span className="text-xs text-purple-500 font-medium">
                {(item.relevance_score * 100).toFixed(0)}% pertinent
              </span>
            )}
            {item.media?.length > 0 && (
              <span className="text-xs text-gray-400">
                {item.media.filter(m => m.type === 'image').length > 0 && `${item.media.filter(m => m.type === 'image').length} img`}
                {item.media.filter(m => m.type === 'video').length > 0 && ` ${item.media.filter(m => m.type === 'video').length} vid`}
              </span>
            )}
            {item.has_video === 1 && (!item.media || !item.media.some(m => m.type === 'video')) && (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700 hover:bg-purple-200 transition-colors"
              >
                ▶ Vidéo disponible
              </a>
            )}
          </div>
          {item.title && !contentIsDuplicate && (
            <h3 className="text-sm font-medium text-gray-900 truncate">{item.title}</h3>
          )}
          {item.content && (
            <div className="relative mt-1">
              <p
                ref={contentRef}
                className={`text-sm text-gray-600 whitespace-pre-line ${expanded ? '' : 'line-clamp-3'}`}
              >
                <Linkify>{item.content}</Linkify>
              </p>
              {(isClamped || expanded) && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="inline-flex items-center gap-0.5 mt-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  {expanded ? (
                    <>Voir moins <ChevronUp className="w-3 h-3" /></>
                  ) : (
                    <>Voir plus <ChevronDown className="w-3 h-3" /></>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Media gallery */}
          <MediaGallery media={item.media} />

          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            {item.author && <span>par {item.author}</span>}
          </div>
        </div>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>
    </div>
  );
}

export default function ItemList({ items, total, query }) {
  if (!items || items.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center text-gray-400">
        {query ? `Aucun résultat pour "${query}"` : 'Aucun item à afficher.'}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {total != null && (
        <p className="text-sm text-gray-500">
          {total} résultat{total > 1 ? 's' : ''}{query ? ` pour "${query}"` : ''}
        </p>
      )}
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </div>
  );
}
