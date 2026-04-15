import { useState, useEffect, useCallback, useRef } from 'react';
import Upload from './components/Upload';
import SearchBar from './components/SearchBar';
import Dashboard from './components/Dashboard';
import ItemList from './components/ItemList';
import IndexingBanner from './components/IndexingBanner';
import ChatPanel from './components/ChatPanel';
import OllamaStatus from './components/OllamaStatus';
import { getStats, getItems, searchItems, semanticSearch, deleteAll, getIndexingStatus, getOllamaStatus, ragChat, getTopics } from './api';
import { Trash2, X, MessageCircle } from 'lucide-react';

function App() {
  const [tab, setTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState(null);
  const [activePlatform, setActivePlatform] = useState(null);
  const [activeMonths, setActiveMonths] = useState([]);  // multiple months
  const [activeYear, setActiveYear] = useState(null);
  const [sortOrder, setSortOrder] = useState('date_desc');
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const currentPageRef = useRef(1);
  const [availableMonths, setAvailableMonths] = useState([]);
  const [loading, setLoading] = useState(false);
  const [aiAnswer, setAiAnswer] = useState(null);
  const [allTopics, setAllTopics] = useState([]);
  const [topicSearch, setTopicSearch] = useState('');
  const [showTopicDropdown, setShowTopicDropdown] = useState(false);
  const sentinelRef = useRef(null);
  const [indexing, setIndexing] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [ollamaAvailable, setOllamaAvailable] = useState(false);

  // Check Ollama on mount
  useEffect(() => {
    getOllamaStatus()
      .then((s) => setOllamaAvailable(s.available && s.has_chat))
      .catch(() => setOllamaAvailable(false));
  }, []);

  // Poll indexing status
  useEffect(() => {
    if (!indexing?.running) return;
    const interval = setInterval(async () => {
      try {
        const s = await getIndexingStatus();
        setIndexing(s);
        if (!s.running) clearInterval(interval);
      } catch { /* ignore */ }
    }, 1000);
    return () => clearInterval(interval);
  }, [indexing?.running]);

  const loadStats = useCallback(async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  }, []);

  const loadItems = useCallback(async (opts = {}, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }
    try {
      const data = await getItems(opts);
      if (append) {
        setItems((prev) => [...prev, ...data.items]);
      } else {
        setItems(data.items);
      }
      setTotal(data.total);
      setHasMore(data.items.length >= 50);
      if (data.months) setAvailableMonths(data.months);
    } catch (e) {
      console.error('Failed to load items:', e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
    loadItems();
    getTopics().then((d) => setAllTopics(d.topics || [])).catch(() => {});
  }, [loadStats, loadItems]);

  const handleSearch = async (q, platform) => {
    setQuery(q);
    setActiveCategory(null);
    setAiAnswer(null);
    currentPageRef.current = 1;
    setHasMore(false);
    setTab('browse');
    setLoading(true);
    try {
      const data = await searchItems(q, { platform });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error('Search failed:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSemanticSearch = async (q, platform) => {
    setQuery(q);
    setActiveCategory(null);
    setAiAnswer(null);
    currentPageRef.current = 1;
    setHasMore(false);
    setTab('browse');
    setLoading(true);
    try {
      // Use RAG chat endpoint — combines FTS + semantic + LLM
      const [chatData, ftsData] = await Promise.all([
        ragChat(q).catch(() => null),
        searchItems(q, { platform }),
      ]);
      if (chatData?.answer) {
        setAiAnswer(chatData.answer);
      }
      setItems(ftsData.items);
      setTotal(ftsData.total);
    } catch (e) {
      console.error('AI search failed:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryClick = (category) => {
    setActiveCategory(category);
    setActivePlatform(null);
    setQuery('');
    setTab('browse');
    loadItems({ category });
  };

  const monthParam = (months) => months.length > 0 ? months.join(',') : undefined;

  const handlePlatformFilter = (platform) => {
    const newPlatform = platform === activePlatform ? null : platform;
    setActivePlatform(newPlatform);
    currentPageRef.current = 1;
    setQuery('');
    loadItems({ category: activeCategory, platform: newPlatform, month: monthParam(activeMonths), sort: sortOrder });
  };

  const handleMonthToggle = (month) => {
    const newMonths = activeMonths.includes(month)
      ? activeMonths.filter((m) => m !== month)
      : [...activeMonths, month];
    setActiveMonths(newMonths);
    currentPageRef.current = 1;
    loadItems({ category: activeCategory, platform: activePlatform, month: monthParam(newMonths), sort: sortOrder });
  };

  const handleYearFilter = (year) => {
    const newYear = year === activeYear ? null : year;
    setActiveYear(newYear);
    setActiveMonths([]);
    currentPageRef.current = 1;
    if (newYear) {
      // Select all months of that year that have data
      const yearMonths = availableMonths.filter((m) => m.month?.startsWith(newYear)).map((m) => m.month);
      setActiveMonths(yearMonths);
      loadItems({ category: activeCategory, platform: activePlatform, month: yearMonths.join(','), sort: sortOrder });
    } else {
      loadItems({ category: activeCategory, platform: activePlatform, sort: sortOrder });
    }
  };

  const handleSortChange = (sort) => {
    setSortOrder(sort);
    currentPageRef.current = 1;
    loadItems({ category: activeCategory, platform: activePlatform, month: monthParam(activeMonths), sort });
  };

  const loadNextPage = useCallback(() => {
    if (loadingMore || !hasMore) return;
    currentPageRef.current += 1;
    loadItems({ category: activeCategory, platform: activePlatform, month: monthParam(activeMonths), sort: sortOrder, page: currentPageRef.current }, true);
  }, [loadingMore, hasMore, activeCategory, activePlatform, activeMonths, sortOrder, loadItems]);

  // Infinite scroll observer
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || loading || loadingMore || items.length === 0 || !hasMore || tab !== 'browse') return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) loadNextPage();
      },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadNextPage, loading, loadingMore, items.length, hasMore, tab]);

  const handleImported = (result) => {
    loadStats();
    loadItems();
    setTab('dashboard');
    if (result?.indexing) {
      setIndexing({ running: true, total: result.imported, done: 0, platform: result.platform });
    }
  };

  const handleClearFilter = () => {
    setQuery('');
    setActiveCategory(null);
    setActivePlatform(null);
    setActiveMonths([]);
    setActiveYear(null);
    currentPageRef.current = 1;
    loadItems({ sort: sortOrder });
  };

  const handleDeleteAll = async () => {
    try {
      await deleteAll();
      setStats(null);
      setItems([]);
      setTotal(0);
      setShowDeleteConfirm(false);
      loadStats();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">
            <span className="text-indigo-600">Tous</span>Mes<span className="text-indigo-600">Likes</span>
          </h1>
          <div className="flex items-center gap-2">
            <nav className="flex gap-1">
              {[
                { id: 'dashboard', label: 'Dashboard' },
                { id: 'browse', label: 'Explorer' },
                ...(ollamaAvailable ? [{ id: 'chat', label: 'Chat IA' }] : []),
                { id: 'upload', label: 'Importer' },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    tab === t.id
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
            <OllamaStatus />
            {stats?.total > 0 && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                title="Supprimer toutes les données"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Indexing banner */}
      {indexing && <IndexingBanner indexing={indexing} />}

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-sm mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Supprimer toutes les données ?</h3>
            <p className="text-sm text-gray-500 mb-4">
              Cette action supprimera tous les items importés ({stats?.total?.toLocaleString('fr-FR')} items). Elle est irréversible.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100"
              >
                Annuler
              </button>
              <button
                onClick={handleDeleteAll}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700"
              >
                Supprimer tout
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Search bar */}
      <div className="max-w-6xl mx-auto px-4 pt-6">
        <SearchBar onSearch={handleSearch} onSemanticSearch={handleSemanticSearch} />
      </div>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {tab === 'dashboard' && (
          <Dashboard stats={stats} onStatsRefresh={loadStats} onCategoryClick={handleCategoryClick} />
        )}

        {tab === 'browse' && (
          <div onClick={() => setShowTopicDropdown(false)}>
            {/* Platform filter bar */}
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              {[
                { id: null, label: 'Tous' },
                { id: 'twitter', label: 'X / Twitter', color: 'sky' },
                { id: 'reddit', label: 'Reddit', color: 'orange' },
                { id: 'instagram', label: 'Instagram', color: 'pink' },
                { id: 'facebook', label: 'Facebook', color: 'blue' },
                { id: 'youtube', label: 'YouTube', color: 'red' },
                { id: 'linkedin', label: 'LinkedIn', color: 'blue' },
                { id: 'chatgpt', label: 'ChatGPT', color: 'emerald' },
                { id: 'claude', label: 'Claude', color: 'amber' },
              ].filter((p) => p.id === null || stats?.by_platform?.some((bp) => bp.platform === p.id))
                .map((p) => (
                <button
                  key={p.id ?? 'all'}
                  onClick={() => handlePlatformFilter(p.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    activePlatform === p.id
                      ? 'bg-indigo-600 text-white ring-2 ring-indigo-300'
                      : p.id === null && !activePlatform
                        ? 'bg-gray-200 text-gray-700'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  {p.label}
                  {p.id && stats?.by_platform && (
                    <span className="ml-1 opacity-60">
                      ({stats.by_platform.find((bp) => bp.platform === p.id)?.count?.toLocaleString('fr-FR')})
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Active filters display */}
            {(query || activeCategory) && (
              <div className="flex items-center gap-2 mb-4">
                {activeCategory && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-indigo-100 text-indigo-700">
                    {activeCategory}
                    <button onClick={handleClearFilter} className="hover:text-indigo-900">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                )}
                {query && (
                  <span className="text-sm text-gray-500">Recherche : "{query}"</span>
                )}
                <button
                  onClick={handleClearFilter}
                  className="text-sm text-indigo-600 hover:text-indigo-800 ml-auto"
                >
                  Effacer les filtres
                </button>
              </div>
            )}
            {/* Sort + Month navigation */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              {/* Sort */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-500">Tri :</span>
                {[
                  { id: 'date_desc', label: 'Plus récent' },
                  { id: 'date_asc', label: 'Plus ancien' },
                  { id: 'imported_desc', label: 'Dernier import' },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => handleSortChange(s.id)}
                    className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                      sortOrder === s.id
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

            </div>

            {/* Year + Month picker */}
            {availableMonths.length > 0 && (() => {
              const MONTH_NAMES = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'];
              const years = [...new Set(availableMonths.map((m) => m.month?.split('-')[0]).filter(Boolean))].sort().reverse();
              const monthsByYear = {};
              for (const m of availableMonths) {
                if (!m.month) continue;
                const [y] = m.month.split('-');
                if (!monthsByYear[y]) monthsByYear[y] = [];
                monthsByYear[y].push(m);
              }

              return (
                <div className="mb-4">
                  {/* Years */}
                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    <span className="text-xs text-gray-500 mr-1">Année :</span>
                    {years.map((y) => {
                      const yearCount = (monthsByYear[y] || []).reduce((s, m) => s + m.count, 0);
                      return (
                        <button
                          key={y}
                          onClick={() => handleYearFilter(y)}
                          className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                            activeYear === y
                              ? 'bg-indigo-600 text-white'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                        >
                          {y} <span className="opacity-60">({yearCount})</span>
                        </button>
                      );
                    })}
                    {activeYear && (
                      <button
                        onClick={() => handleYearFilter(null)}
                        className="px-2 py-1 rounded-md text-xs text-gray-400 hover:text-gray-600"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>

                  {/* Months of selected year */}
                  {activeYear && monthsByYear[activeYear] && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-gray-500 mr-1">Mois :</span>
                      {monthsByYear[activeYear]
                        .sort((a, b) => a.month.localeCompare(b.month))
                        .map((m) => {
                          const monthNum = parseInt(m.month.split('-')[1], 10);
                          const isActive = activeMonths.includes(m.month);
                          return (
                            <button
                              key={m.month}
                              onClick={() => handleMonthToggle(m.month)}
                              className={`px-2 py-1 rounded-md text-xs font-medium transition-all ${
                                isActive
                                  ? 'bg-indigo-500 text-white'
                                  : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200'
                              }`}
                            >
                              {MONTH_NAMES[monthNum - 1]} <span className="opacity-60">({m.count})</span>
                            </button>
                          );
                        })}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Category filter */}
            {allTopics.length > 0 && (
              <div className="relative mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Thématique :</span>
                  {activeCategory ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                      {activeCategory}
                      <button onClick={() => { setActiveCategory(null); currentPageRef.current = 1; loadItems({ platform: activePlatform, month: monthParam(activeMonths), sort: sortOrder }); }}>
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ) : (
                    <div className="relative flex-1 max-w-xs">
                      <input
                        type="text"
                        value={topicSearch}
                        onChange={(e) => { setTopicSearch(e.target.value); setShowTopicDropdown(true); }}
                        onFocus={() => setShowTopicDropdown(true)}
                        placeholder="Rechercher une thématique..."
                        className="w-full px-2.5 py-1 rounded-md border border-gray-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      />
                      {showTopicDropdown && (
                        <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-48 overflow-y-auto">
                          {allTopics
                            .filter((t) => !topicSearch || t.label.toLowerCase().includes(topicSearch.toLowerCase()))
                            .slice(0, 20)
                            .map((t) => (
                              <button
                                key={t.label}
                                onClick={() => {
                                  handleCategoryClick(t.label);
                                  setTopicSearch('');
                                  setShowTopicDropdown(false);
                                }}
                                className="w-full text-left px-3 py-1.5 text-xs hover:bg-indigo-50 flex justify-between"
                              >
                                <span>{t.label}</span>
                                <span className="text-gray-400">{t.count}</span>
                              </button>
                            ))}
                          {allTopics.filter((t) => !topicSearch || t.label.toLowerCase().includes(topicSearch.toLowerCase())).length === 0 && (
                            <div className="px-3 py-2 text-xs text-gray-400">Aucune thématique trouvée</div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* AI Answer banner */}
            {aiAnswer && (
              <div className="mb-4 bg-purple-50 border border-purple-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-purple-600 text-sm font-semibold">Réponse IA</span>
                  <button onClick={() => setAiAnswer(null)} className="ml-auto text-purple-400 hover:text-purple-600">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <p className="text-sm text-gray-700 whitespace-pre-line">{aiAnswer}</p>
              </div>
            )}

            {loading ? (
              <div className="text-center py-12 text-gray-400">Chargement...</div>
            ) : (
              <>
                <ItemList items={items} total={total} query={query} />

                {/* Infinite scroll sentinel */}
                {hasMore && (
                  <div ref={sentinelRef} className="py-8 text-center">
                    {loadingMore && (
                      <span className="text-sm text-gray-400">Chargement...</span>
                    )}
                  </div>
                )}
                {!hasMore && items.length > 0 && (
                  <div className="py-6 text-center text-xs text-gray-400">
                    {items.length} / {total} items affichés
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {tab === 'chat' && <ChatPanel />}

        {tab === 'upload' && <Upload onImported={handleImported} />}
      </main>
    </div>
  );
}

export default App;
