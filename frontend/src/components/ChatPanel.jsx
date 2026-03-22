import { useState, useRef, useEffect } from 'react';
import { MessageCircle, Send, Loader2, ExternalLink, Bot, User } from 'lucide-react';
import { ragChat } from '../api';

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const query = input.trim();
    if (!query || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setLoading(true);

    try {
      const result = await ragChat(query);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.answer,
          sources: result.sources,
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: e.message },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex flex-col" style={{ height: '70vh' }}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <MessageCircle className="w-4 h-4 text-purple-600" />
          Chat avec tes données
          <span className="text-xs font-normal text-purple-500 bg-purple-50 px-2 py-0.5 rounded-full">
            Ollama
          </span>
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          Pose une question sur tes likes, bookmarks et tweets
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-12">
            <Bot className="w-8 h-8 mx-auto mb-3 text-purple-300" />
            <p>Pose-moi une question !</p>
            <p className="text-xs mt-2 text-gray-300">
              Ex: "C'est quoi le projet qui parlait de tricot ?"
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role !== 'user' && (
              <div className="shrink-0 w-7 h-7 rounded-full bg-purple-100 flex items-center justify-center">
                <Bot className="w-4 h-4 text-purple-600" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : msg.role === 'error'
                    ? 'bg-red-50 text-red-600'
                    : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {/* Sources */}
              {msg.sources?.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-200/50">
                  <p className="text-xs text-gray-500 mb-1.5">Sources :</p>
                  <div className="space-y-1">
                    {msg.sources.slice(0, 5).map((s) => (
                      <div key={s.id} className="flex items-center gap-1.5 text-xs">
                        <span className="text-gray-400">[{s.platform}]</span>
                        <span className="truncate text-gray-600">
                          {s.title || 'Sans titre'}
                        </span>
                        {s.url && (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 text-indigo-500 hover:text-indigo-700"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="shrink-0 w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center">
                <User className="w-4 h-4 text-indigo-600" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-7 h-7 rounded-full bg-purple-100 flex items-center justify-center">
              <Bot className="w-4 h-4 text-purple-600" />
            </div>
            <div className="bg-gray-100 rounded-2xl px-4 py-2.5">
              <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pose une question sur tes données..."
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm
                       focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent
                       disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-xl bg-purple-600 text-white
                       hover:bg-purple-700 disabled:opacity-50 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
