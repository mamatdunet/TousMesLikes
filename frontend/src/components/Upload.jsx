import { useState, useRef, useEffect } from 'react';
import { Upload as UploadIcon, CheckCircle, AlertCircle, Loader2, Info, ExternalLink, Check } from 'lucide-react';
import { uploadFile, getImportHistory } from '../api';

const PLATFORM_GROUPS = [
  {
    name: 'X / Twitter',
    icon: '𝕏',
    color: 'sky',
    howTo: 'Paramètres > Votre compte > Télécharger une archive',
    howToUrl: 'https://x.com/settings/download_your_data',
    items: [
      { id: 'twitter_likes', label: 'Likes', hint: 'like.js', path: 'data/like.js' },
      { id: 'twitter_tweets', label: 'Tweets', hint: 'tweet.js', path: 'data/tweets.js' },
      { id: 'twitter_bookmarks', label: 'Bookmarks', hint: 'bookmark.js', path: 'data/bookmark.js' },
    ],
  },
  {
    name: 'Facebook',
    icon: 'f',
    color: 'blue',
    howTo: 'Paramètres > Vos informations Facebook > Télécharger vos informations (format JSON)',
    howToUrl: 'https://www.facebook.com/dyi/',
    items: [
      { id: 'facebook_likes', label: 'Likes / Réactions', hint: 'likes_and_reactions.json', path: 'your_facebook_activity/comments_and_reactions/likes_and_reactions.json' },
      { id: 'facebook_comments', label: 'Commentaires', hint: 'comments.json', path: 'your_facebook_activity/comments_and_reactions/comments.json' },
      { id: 'facebook_pages', label: 'Pages likées', hint: "pages_you've_liked.json", path: "your_facebook_activity/pages/pages_you've_liked.json" },
      { id: 'facebook_posts', label: 'Mes posts', hint: 'your_posts__check_ins__*.json', path: 'your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json' },
      { id: 'facebook_group_posts', label: 'Posts groupes', hint: 'group_posts_and_comments.json', path: 'your_facebook_activity/groups/group_posts_and_comments.json' },
      { id: 'facebook_group_comments', label: 'Commentaires groupes', hint: 'your_comments_in_groups.json', path: 'your_facebook_activity/groups/your_comments_in_groups.json' },
      { id: 'facebook_other_pages', label: 'Posts sur autres pages', hint: 'posts_on_other_pages_and_profiles.json', path: 'your_facebook_activity/posts/posts_on_other_pages_and_profiles.json' },
    ],
  },
  {
    name: 'YouTube',
    icon: '▶',
    color: 'red',
    howTo: 'Google Takeout > cocher YouTube > choisir format JSON',
    howToUrl: 'https://takeout.google.com/',
    items: [
      { id: 'youtube_history', label: 'Historique', hint: 'watch-history.json', path: 'Takeout/YouTube and YouTube Music/history/watch-history.json' },
      { id: 'youtube_likes_json', label: 'Likes (JSON)', hint: 'likes.json', path: 'Takeout/YouTube and YouTube Music/playlists/likes.json' },
      { id: 'youtube_likes_csv', label: 'Likes (CSV)', hint: 'likes.csv', path: 'Takeout/YouTube and YouTube Music/playlists/likes.csv' },
      { id: 'youtube_playlist', label: 'Playlist', hint: 'Playlist-*.csv ou JSON', path: 'Takeout/YouTube and YouTube Music/playlists/Playlist-TITRE.csv' },
      { id: 'youtube_comments', label: 'Commentaires', hint: 'my-comments.html', path: 'Takeout/YouTube and YouTube Music/my-comments/my-comments.html' },
    ],
  },
  {
    name: 'LinkedIn',
    icon: 'in',
    color: 'blue',
    howTo: 'Paramètres > Confidentialité des données > Obtenir une copie (export Complet, 24-72h)',
    howToUrl: 'https://www.linkedin.com/mypreferences/d/download-my-data',
    items: [
      { id: 'linkedin', label: 'Auto-detect', hint: 'CSV (auto-détection)', path: 'Basic_LinkedInDataExport_*/...csv' },
      { id: 'linkedin_reactions', label: 'Réactions', hint: 'Reactions.csv', path: 'Reactions.csv' },
      { id: 'linkedin_comments', label: 'Commentaires', hint: 'Comments.csv', path: 'Comments.csv' },
      { id: 'linkedin_shares', label: 'Mes posts', hint: 'Shares.csv', path: 'Shares.csv' },
      { id: 'linkedin_saved', label: 'Sauvegardés', hint: 'SavedItems.csv', path: 'SavedItems.csv' },
    ],
  },
  {
    name: 'Instagram',
    icon: '📷',
    color: 'pink',
    howTo: 'Paramètres > Votre activité > Télécharger vos informations (format JSON)',
    howToUrl: 'https://www.instagram.com/download/request/',
    items: [
      { id: 'instagram', label: 'Likes', hint: 'liked_posts.json', path: 'your_instagram_activity/likes/liked_posts.json' },
    ],
  },
  {
    name: 'Reddit',
    icon: '🤖',
    color: 'orange',
    howTo: 'Paramètres > Demander vos données (GDPR) ou via le lien ci-dessous',
    howToUrl: 'https://www.reddit.com/settings/data-request',
    items: [
      { id: 'reddit', label: 'Upvotes / Données', hint: 'CSV ou JSON', path: 'upvoted_posts.csv ou saved_posts.csv' },
    ],
  },
  {
    name: 'ChatGPT',
    icon: '🤖',
    color: 'emerald',
    howTo: 'Paramètres > Data Controls > Export data',
    howToUrl: 'https://chatgpt.com/#settings/DataControls',
    items: [
      { id: 'chatgpt', label: 'Conversations', hint: 'conversations.json', path: 'conversations.json' },
    ],
  },
  {
    name: 'Claude',
    icon: '🧠',
    color: 'amber',
    howTo: 'Paramètres > Account > Export data (bouton en bas)',
    howToUrl: 'https://claude.ai/settings',
    items: [
      { id: 'claude', label: 'Conversations', hint: 'JSON export', path: 'conversations.json' },
    ],
  },
];

function InfoTooltip({ path, activeTooltip, setActiveTooltip, tooltipId }) {
  const btnRef = useRef();
  const isOpen = activeTooltip === tooltipId;

  const handleClick = (e) => {
    e.stopPropagation();
    setActiveTooltip(isOpen ? null : tooltipId);
  };

  // Compute position relative to viewport
  const [pos, setPos] = useState(null);
  const updatePos = () => {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({ top: rect.top - 8, left: rect.left + rect.width / 2 });
    }
  };

  return (
    <span className="inline-block">
      <button
        ref={btnRef}
        onClick={(e) => { handleClick(e); updatePos(); }}
        className="ml-1 text-gray-400 hover:text-indigo-500 transition-colors"
        title="Chemin du fichier"
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      {isOpen && pos && (
        <span
          className="fixed z-[9999] px-3 py-2 rounded-lg bg-gray-900 text-white text-xs shadow-lg whitespace-nowrap pointer-events-none"
          style={{ top: pos.top, left: pos.left, transform: 'translate(-50%, -100%)' }}
        >
          <span className="font-mono">{path}</span>
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  );
}

// Map parser IDs to platform+type for matching import history
const PARSER_TO_PLATFORM_TYPE = {
  twitter_likes: { platform: 'twitter', type: 'like' },
  twitter_tweets: { platform: 'twitter', type: 'tweet' },
  twitter_bookmarks: { platform: 'twitter', type: 'bookmark' },
  facebook_likes: { platform: 'facebook', type: 'reaction' },
  facebook_pages: { platform: 'facebook', type: 'page_like' },
  facebook_posts: { platform: 'facebook', type: 'post' },
  facebook_comments: { platform: 'facebook', type: 'comment' },
  facebook_group_posts: { platform: 'facebook', type: 'group_post' },
  facebook_group_comments: { platform: 'facebook', type: 'group_comment' },
  facebook_other_pages: { platform: 'facebook', type: 'wall_post' },
  youtube_history: { platform: 'youtube', type: 'watch' },
  youtube_likes_json: { platform: 'youtube', type: 'like' },
  youtube_likes_csv: { platform: 'youtube', type: 'like' },
  youtube_playlist: { platform: 'youtube', type: 'playlist' },
  youtube_comments: { platform: 'youtube', type: 'comment' },
  linkedin: { platform: 'linkedin' },
  linkedin_reactions: { platform: 'linkedin', type: 'like' },
  linkedin_comments: { platform: 'linkedin', type: 'comment' },
  linkedin_shares: { platform: 'linkedin', type: 'post' },
  linkedin_saved: { platform: 'linkedin', type: 'saved' },
  instagram: { platform: 'instagram', type: 'like' },
  reddit: { platform: 'reddit', type: 'upvote' },
  chatgpt: { platform: 'chatgpt' },
  claude: { platform: 'claude' },
};

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function Upload({ onImported }) {
  const [selectedId, setSelectedId] = useState('twitter_likes');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState(null);
  const [importHistory, setImportHistory] = useState([]);
  const fileRef = useRef();

  const loadHistory = () => {
    getImportHistory().then((data) => setImportHistory(data.imports || [])).catch(() => {});
  };

  useEffect(() => { loadHistory(); }, []);

  // Find import info for a given parser ID
  const getImportInfo = (parserId) => {
    const mapping = PARSER_TO_PLATFORM_TYPE[parserId];
    if (!mapping) return null;
    const matches = importHistory.filter((h) =>
      h.platform === mapping.platform && (!mapping.type || h.type === mapping.type)
    );
    if (matches.length === 0) return null;
    const totalCount = matches.reduce((sum, m) => sum + m.count, 0);
    const lastImport = matches.reduce((latest, m) =>
      !latest || m.last_import > latest ? m.last_import : latest, null
    );
    return { count: totalCount, lastImport };
  };

  // Get total imported for a platform group
  const getGroupImportCount = (group) => {
    return group.items.reduce((sum, item) => {
      const info = getImportInfo(item.id);
      return sum + (info?.count || 0);
    }, 0);
  };

  const handleUpload = async () => {
    const file = fileRef.current?.files[0];
    if (!file) return;

    setLoading(true);
    setStatus(null);
    try {
      const result = await uploadFile(file, selectedId);
      setStatus({ type: 'success', message: `${result.imported} items importés` });
      fileRef.current.value = '';
      onImported?.(result);
      loadHistory();
    } catch (e) {
      setStatus({ type: 'error', message: e.message });
    } finally {
      setLoading(false);
    }
  };

  const selectedItem = PLATFORM_GROUPS.flatMap((g) => g.items).find((i) => i.id === selectedId);

  return (
    <div onClick={() => setActiveTooltip(null)}>
      <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <UploadIcon className="w-5 h-5" />
        Importer des données
      </h2>

      <div className="flex gap-6 items-start">
        {/* Left: all platform groups, always open */}
        <div className="flex-1 space-y-4">
          {PLATFORM_GROUPS.map((group) => {
            const groupCount = getGroupImportCount(group);
            return (
              <div key={group.name} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-visible">
                {/* Group header */}
                <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100">
                  <span className="text-sm font-semibold text-gray-800">{group.name}</span>
                  {groupCount > 0 && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                      <Check className="w-3 h-3" />
                      {groupCount.toLocaleString('fr-FR')}
                    </span>
                  )}
                  <div className="ml-auto flex items-start gap-1.5 text-xs text-indigo-600">
                    <span className="text-gray-400">{group.howTo}</span>
                    {group.howToUrl && (
                      <a
                        href={group.howToUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-0.5 shrink-0 hover:text-indigo-800"
                        title={group.howTo}
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>

                {/* Import type buttons — always visible */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 p-3">
                  {group.items.map((item) => {
                    const info = getImportInfo(item.id);
                    return (
                      <button
                        key={item.id}
                        onClick={() => setSelectedId(item.id)}
                        className={`flex flex-col gap-0.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-all text-left ${
                          selectedId === item.id
                            ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-400 shadow-sm'
                            : info ? 'bg-green-50 text-gray-600 hover:bg-green-100 border border-green-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-100'
                        }`}
                      >
                        <span className="flex items-center gap-1">
                          <span className="truncate">{item.label}</span>
                          <InfoTooltip path={item.path} tooltipId={item.id} activeTooltip={activeTooltip} setActiveTooltip={setActiveTooltip} />
                        </span>
                        {info && (
                          <span className="flex items-center gap-1 text-[10px] text-green-600 font-normal">
                            <Check className="w-3 h-3" />
                            {info.count.toLocaleString('fr-FR')} items — {formatDate(info.lastImport)}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: sticky import panel */}
        <div className="w-72 shrink-0 sticky top-4">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-800">
              {selectedItem ? (
                <>Import : <span className="text-indigo-600">{selectedItem.label}</span></>
              ) : 'Sélectionnez un type'}
            </h3>

            {selectedItem && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">
                  Fichier attendu : <span className="font-mono text-gray-700">{selectedItem.hint}</span>
                </label>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".js,.json,.csv,.html"
                  className="block w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3
                             file:rounded-lg file:border-0 file:text-xs file:font-medium
                             file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100
                             cursor-pointer"
                />
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={loading || !selectedItem}
              className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 text-white text-sm font-medium
                         hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed
                         flex items-center justify-center gap-2 transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Import...
                </>
              ) : (
                <>
                  <UploadIcon className="w-4 h-4" />
                  Importer
                </>
              )}
            </button>

            {status && (
              <div
                className={`flex items-center gap-2 p-2.5 rounded-lg text-xs ${
                  status.type === 'success'
                    ? 'bg-green-50 text-green-700'
                    : 'bg-red-50 text-red-700'
                }`}
              >
                {status.type === 'success' ? (
                  <CheckCircle className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0" />
                )}
                {status.message}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
