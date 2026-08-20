'use client';
import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Trash2, Plus, Scale, BookOpen, Loader2, MessageSquare, ExternalLink, FileText, AlertCircle, CheckCircle, Clock, Info, Brain, Lightbulb, ChevronDown, ChevronUp, LogOut } from 'lucide-react';

// ─── Colour Tokens ───────────────────────────────────────────────────────────
// bg-page    : #ede8de   (warm parchment)
// bg-sidebar : #e2dbd0   (slightly darker beige)
// bg-card    : #ffffff   (white)
// bg-card-alt: #f7f3ec   (cream card)
// accent     : #74603e   (rich brown – matches the user's original colour)
// accent-dk  : #5c4b2f   (darker brown for hover)
// text-head  : #2d1f0e   (very dark brown, almost black)
// text-body  : #4a3728   (medium brown)
// text-muted : #8a7462   (muted tan)
// border     : rgba(116,96,62,0.20)
// ─────────────────────────────────────────────────────────────────────────────


// ─── Types ────────────────────────────────────────────────────────────────────

interface ReasoningStep {
  step_number: number;
  step_type: string;
  title: string;
  explanation: string;
  confidence: number;
  supporting_sources: string[];
  legal_provisions: string[];
}

interface PrecedentExplanation {
  precedent_title: string;
  similarity_score: number;
  matching_factors: string[];
  different_factors: string[];
  key_excerpt: string;
  relevance_explanation: string;
  citation: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  messageType?: 'clarification' | 'information_gathering' | 'final_response';
  infoCollected?: Record<string, string>;
  infoNeeded?: string[];
  reasoningSteps?: ReasoningStep[];
  precedentExplanations?: PrecedentExplanation[];
}

interface ThreadSummary {
  thread_id: string;
  title: string | null;
  status: 'analyzing' | 'gathering_info' | 'completed';
  message_count: number;
  updated_at: string;
}

interface MessageOut {
  role: string;
  content: string;
  metadata: Record<string, any> | null;
  created_at: string;
}

const LegalAssistChat: React.FC = () => {
  const router = useRouter();
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<{ id: number; email: string; full_name: string } | null>(null);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sources, setSources] = useState<any[]>([]);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [conversationStatus, setConversationStatus] = useState<string>('ready');
  const [infoCollected, setInfoCollected] = useState<Record<string, string>>({});
  const [infoNeeded, setInfoNeeded] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  useEffect(() => { scrollToBottom(); }, [messages, streamingMessage]);
  useEffect(() => {
    // Auth check on mount
    const token = localStorage.getItem('auth_token');
    const userStr = localStorage.getItem('auth_user');
    if (!token || !userStr) {
      router.push('/auth');
      return;
    }
    setAuthToken(token);
    try { setAuthUser(JSON.parse(userStr)); } catch { router.push('/auth'); return; }
  }, []);
  useEffect(() => {
    if (authToken) loadThreads();
  }, [authToken]);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '48px';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  // ── API calls ───────────────────────────────────────────────────────────────

  const authHeaders = (): Record<string, string> => ({
    'Authorization': `Bearer ${authToken}`,
  });

  const signOut = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    router.push('/auth');
  };

  const loadThreads = async () => {
    try {
      const res = await fetch(`${API_BASE}/threads`, { headers: authHeaders() });
      if (res.status === 401) { signOut(); return; }
      if (res.ok)
        setThreads(await res.json());
    } catch (err) {
      console.error('Failed to load threads:', err);
      setError('Unable to load conversation history');
    }
  };

  const createNewThread = () => {
    // Don't pre-generate the UUID here — backend generates it on first message.
    setCurrentThreadId(null);
    setMessages([]);
    setSources([]);
    setStreamingMessage('');
    setError(null);
    setInput('');
    setInfoCollected({});
    setInfoNeeded([]);
    setConversationStatus('ready');
  };

  const loadThread = async (threadId: string) => {
    try {
      setError(null);
      setStreamingMessage('');
      const res = await fetch(`${API_BASE}/threads/${threadId}`, { headers: authHeaders() });
      if (res.status === 401) { signOut(); return; }
      if (!res.ok) throw new Error('Failed to load thread');
      const data: MessageOut[] = await res.json();

      setCurrentThreadId(threadId);

      const formatted: Message[] = data.map((m, idx) => {
        const isLastAI = m.role === 'assistant' && idx === data.length - 1;
        const msg: Message = {
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: new Date(m.created_at),
        };
        // Restore reasoning + explainability from stored metadata
        if (isLastAI && m.metadata) {
          const meta = m.metadata;
          if (meta.reasoning_steps?.length) msg.reasoningSteps = meta.reasoning_steps;
          if (meta.precedent_explanations?.length) msg.precedentExplanations = meta.precedent_explanations;
          if (meta.message_type) msg.messageType = meta.message_type;
        } else if (m.role === 'assistant' && m.metadata?.message_type) {
          msg.messageType = m.metadata.message_type;
          if (m.metadata.message_type === 'information_gathering') {
            msg.infoCollected = m.metadata.info_collected || {};
          }
        }
        return msg;
      });

      setMessages(formatted);
      setSources([]);
      setInfoCollected({});
      setInfoNeeded([]);

      // Restore status from the latest AI message metadata
      const lastAI = data.filter(m => m.role === 'assistant').pop();
      if (lastAI?.metadata) {
        setConversationStatus(lastAI.metadata.message_type === 'final_response' ? 'completed' : 'gathering_info');
      }
    } catch (err) {
      console.error('Failed to load thread:', err);
      setError('Unable to load this conversation');
    }
  };

  const deleteThread = async (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation?')) return;
    try {
      const res = await fetch(`${API_BASE}/threads/${threadId}`, { method: 'DELETE', headers: authHeaders() });
      if (res.status === 401) { signOut(); return; }
      if (!res.ok) throw new Error('Delete failed');
      loadThreads();
      if (currentThreadId === threadId) createNewThread();
    } catch (err) {
      setError('Unable to delete conversation');
    }
  };

  const sendMessage = async (text: string = input) => {
    if (!text.trim() || isLoading) return;

    const optimisticThreadId = currentThreadId; // may be null for new chats
    setMessages(prev => [...prev, { role: 'user', content: text, timestamp: new Date() }]);
    setInput('');
    setIsLoading(true);
    setStreamingMessage('');
    setSources([]);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          query: text,
          thread_id: optimisticThreadId,   // null → backend generates UUID
          include_reasoning: true,
          include_prediction: true,
        }),
      });
      if (res.status === 401) { signOut(); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let accumulatedText = '';
      let messageType: string | null = null;
      let reasoningSteps: ReasoningStep[] = [];
      let precedentExplanations: PrecedentExplanation[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        for (const line of decoder.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'setup') {
              // Backend assigned a new thread_id
              setCurrentThreadId(data.thread_id);
            } else if (data.type === 'metadata') {
              // Confirmation of thread_id (sent on every request)
              if (!currentThreadId) setCurrentThreadId(data.thread_id);
            } else if (data.type === 'clarification') {
              accumulatedText = data.content;
              messageType = 'clarification';
              setStreamingMessage(accumulatedText);
              setConversationStatus('clarifying');
            } else if (data.type === 'information_gathering') {
              accumulatedText = data.content;
              messageType = 'information_gathering';
              setInfoCollected(data.info_collected || {});
              setInfoNeeded(data.info_needed || []);
              setStreamingMessage(accumulatedText);
              setConversationStatus('gathering_info');
            } else if (data.type === 'token') {
              accumulatedText += data.content;
              messageType = 'final_response';
              setStreamingMessage(accumulatedText);
              setConversationStatus('generating');
            } else if (data.type === 'sources') {
              setSources(data.sources || []);
            } else if (data.type === 'reasoning') {
              reasoningSteps = data.steps || [];
            } else if (data.type === 'precedent_explanations') {
              precedentExplanations = data.explanations || [];
            } else if (data.type === 'done') {
              messageType = data.message_type || 'final_response';
              if (accumulatedText) {
                const msg: Message = {
                  role: 'assistant',
                  content: accumulatedText,
                  timestamp: new Date(),
                  messageType: messageType as any,
                  reasoningSteps: data.reasoning_steps || reasoningSteps,
                  precedentExplanations: data.precedent_explanations || precedentExplanations,
                };
                if (messageType === 'information_gathering') {
                  msg.infoCollected = data.info_collected;
                  msg.infoNeeded = data.info_needed;
                }
                setMessages(prev => [...prev, msg]);
              }
              setStreamingMessage('');
              setConversationStatus(
                messageType === 'final_response' ? 'completed' :
                  messageType === 'information_gathering' ? 'gathering_info' : 'clarifying'
              );
              // Ensure thread_id is set from done payload
              if (data.thread_id && !currentThreadId) setCurrentThreadId(data.thread_id);
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          } catch (e) { console.warn('Parse error', e); }
        }
      }
      loadThreads();
    } catch (err) {
      console.error('Send failed:', err);
      setError('Failed to get response. Please try again.');
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ I encountered an error. Please try again.',
        timestamp: new Date(),
      }]);
      setStreamingMessage('');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const formatMessage = (text: string): string => {
    if (!text) return '';
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/```([\s\S]*?)```/g, '<pre class="bg-[#f0ebe1] border border-[#c8b89a] p-3 rounded-lg my-2 overflow-x-auto text-[#2d1f0e]"><code>$1</code></pre>');
    text = text.replace(/`([^`]+)`/g, '<code class="bg-[#f0ebe1] border border-[#c8b89a] px-2 py-0.5 rounded text-sm text-[#74603e]">$1</code>');
    text = text.replace(/\n/g, '<br/>');
    return text;
  };

  const formatTime = (date?: Date) =>
    date ? new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(date) : '';

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

  const getStatusColor = (s: string) => ({
    analyzing: 'bg-amber-100 text-amber-800 border-amber-300',
    gathering_info: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    completed: 'bg-green-100 text-green-800 border-green-300',
    clarifying: 'bg-orange-100 text-orange-800 border-orange-300',
    generating: 'bg-[#f0ebe1] text-[#74603e] border-[#c8b89a]',
  } as Record<string, string>)[s] || 'bg-stone-100 text-stone-600 border-stone-300';

  const getStatusIcon = (s: string) => ({
    analyzing: <Loader2 className="w-4 h-4 animate-spin" />,
    gathering_info: <Info className="w-4 h-4" />,
    completed: <CheckCircle className="w-4 h-4" />,
    clarifying: <AlertCircle className="w-4 h-4" />,
    generating: <Loader2 className="w-4 h-4 animate-spin" />,
  } as Record<string, React.ReactNode>)[s] || <Clock className="w-4 h-4" />;

  const getStatusText = (s: string) => ({
    analyzing: 'Analyzing',
    gathering_info: 'Gathering Info',
    completed: 'Completed',
    clarifying: 'Clarifying',
    generating: 'Generating',
  } as Record<string, string>)[s] || 'Ready';

  const getConfidenceColor = (c: number) => c >= 0.85 ? 'text-green-700' : c >= 0.70 ? 'text-yellow-700' : 'text-orange-700';
  const getConfidenceEmoji = (c: number) => c >= 0.85 ? '🟢' : c >= 0.70 ? '🟡' : '🟠';

  // ── Sub-components ──────────────────────────────────────────────────────────

  const ReasoningStepCard: React.FC<{ step: ReasoningStep; index: number }> = ({ step, index }) => {
    const [expanded, setExpanded] = useState(index === 0);
    return (
      <div className="bg-white rounded-xl border border-[rgba(116,96,62,0.20)] overflow-hidden shadow-sm">
        <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-4 hover:bg-[#f7f3ec] transition-colors">
          <div className="flex items-center gap-3">
            <span className="text-[#74603e] font-semibold">Step {step.step_number}</span>
            <span className="text-[#2d1f0e] font-medium">{step.title}</span>
            {/* <span className={`text-sm ${getConfidenceColor(step.confidence)}`}>{getConfidenceEmoji(step.confidence)} {(step.confidence * 100).toFixed(0)}%</span> */}
          </div>
          {expanded ? <ChevronUp className="w-5 h-5 text-[#8a7462]" /> : <ChevronDown className="w-5 h-5 text-[#8a7462]" />}
        </button>
        {expanded && (
          <div className="p-4 pt-0 space-y-3 border-t border-[rgba(116,96,62,0.10)]">
            <p className="text-[#4a3728]">{step.explanation}</p>
            {step.legal_provisions.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {step.legal_provisions.map((p, i) => (
                  <span key={i} className="px-3 py-1 bg-[#f0ebe1] text-[#74603e] rounded-full text-sm border border-[#c8b89a]">📜 {p}</span>
                ))}
              </div>
            )}
            {step.supporting_sources.length > 0 && (
              <div className="text-sm text-[#8a7462]">📚 Based on {step.supporting_sources.length} precedent(s)</div>
            )}
          </div>
        )}
      </div>
    );
  };

  const PrecedentCard: React.FC<{ precedent: PrecedentExplanation; index: number }> = ({ precedent, index }) => {
    const [expanded, setExpanded] = useState(false);
    return (
      <div className="bg-white rounded-xl border border-[rgba(116,96,62,0.20)] overflow-hidden shadow-sm">
        <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-4 hover:bg-[#f7f3ec] transition-colors">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="text-[#74603e] font-semibold">#{index + 1}</span>
            <span className="text-[#2d1f0e] font-medium truncate">{precedent.precedent_title}</span>
            <span className="text-sm text-[#74603e] font-medium">{(precedent.similarity_score * 100).toFixed(0)}% match</span>
          </div>
          {expanded ? <ChevronUp className="w-5 h-5 text-[#8a7462]" /> : <ChevronDown className="w-5 h-5 text-[#8a7462]" />}
        </button>
        {expanded && (
          <div className="p-4 pt-0 space-y-4 border-t border-[rgba(116,96,62,0.10)]">
            <div>
              <h4 className="text-sm font-semibold text-[#74603e] mb-2">Why This Matters:</h4>
              <p className="text-[#4a3728] text-sm">{precedent.relevance_explanation}</p>
            </div>
            {precedent.matching_factors.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-green-700 mb-2">✓ Similarities:</h4>
                <ul className="space-y-1">
                  {precedent.matching_factors.map((f, i) => (
                    <li key={i} className="text-sm text-[#4a3728] flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" /><span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {precedent.different_factors.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-orange-700 mb-2">⚠ Differences:</h4>
                <ul className="space-y-1">
                  {precedent.different_factors.map((f, i) => (
                    <li key={i} className="text-sm text-[#4a3728] flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" /><span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {precedent.key_excerpt && (
              <div className="bg-[#f7f3ec] p-3 rounded-lg border-l-4 border-[#74603e]">
                <p className="text-sm text-[#4a3728] italic">"{precedent.key_excerpt}"</p>
              </div>
            )}
            {precedent.citation && (
              <a href={precedent.citation} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-[#74603e] hover:text-[#5c4b2f] text-sm font-medium">
                <ExternalLink className="w-4 h-4" /> View Full Precedent
              </a>
            )}
          </div>
        )}
      </div>
    );
  };

  const InfoCollectedSummary: React.FC<{ collectedInfo: Record<string, string> }> = ({ collectedInfo }) => {
    if (!collectedInfo || Object.keys(collectedInfo).length === 0) return null;
    return (
      <div className="bg-[#f7f3ec] border border-[#c8b89a] rounded-xl p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Info className="w-5 h-5 text-[#74603e]" />
            <h3 className="text-[#2d1f0e] font-semibold">Information Collected</h3>
          </div>
          <div className="px-3 py-1 rounded-lg border border-green-300 bg-green-50 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-xs font-medium text-green-700">{Object.keys(collectedInfo).length} items</span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(collectedInfo).filter(([k]) => k !== 'additional_info').map(([key, value]) => (
            <div key={key} className="bg-white rounded-lg p-3 border border-[rgba(116,96,62,0.15)] shadow-sm">
              <div className="text-sm text-[#74603e] font-medium mb-1">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
              <div className="text-[#2d1f0e] text-sm">{value}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderInfoProgress = (msg: Message) => {
    if (msg.messageType !== 'information_gathering') return null;
    const collected = Object.keys(msg.infoCollected || {}).length;
    const needed = (msg.infoNeeded || []).length;
    const total = collected + needed;
    if (total === 0) return null;
    return (
      <div className="mt-3 p-3 bg-[#f7f3ec] rounded-lg border border-[#c8b89a]">
        <div className="flex items-center gap-2 mb-2">
          <Info className="w-4 h-4 text-[#74603e]" />
          <span className="text-sm font-medium text-[#74603e]">Information Collection Progress</span>
        </div>
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-[#8a7462]">
            <span>Collected: {collected}</span><span>Remaining: {needed}</span>
          </div>
          <div className="w-full bg-[#e2dbd0] rounded-full h-2">
            <div className="bg-[#74603e] h-2 rounded-full transition-all duration-300" style={{ width: `${(collected / total) * 100}%` }} />
          </div>
        </div>
      </div>
    );
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-[#ede8de] relative">

      {/* Decorative background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 0 }}>
        <div className="fixed -top-[10%] -right-[10%] w-[50%] h-[70%] rounded-full" style={{ background: '#74603e38', filter: 'blur(75px)' }} />
        <div className="fixed -bottom-[10%] right-[20%] w-[30%] h-[40%] rounded-full" style={{ background: '#d4812e2a', filter: 'blur(75px)' }} />
        <div className="fixed inset-0" style={{ opacity: 0.04, backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
      </div>

      <div className="relative flex flex-1 overflow-hidden" style={{ zIndex: 1 }}>

        {/* ── Sidebar ────────────────────────────────────────────────────────── */}
        <div className="w-80 bg-[#e2dbd0]/90 border-r border-[#c8b89a] flex flex-col shadow-md backdrop-blur-sm">
          <div className="p-6 border-b border-[#c8b89a] bg-[#d8d0c4]">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-[#74603e]/15 rounded-lg border border-[#c8b89a]">
                <Scale className="w-6 h-6 text-[#74603e]" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-black">Family Law</h1>
                <p className="text-xs text-gray-600">Legal Assistant</p>
              </div>
            </div>
            {authUser && (
              <div className="flex items-center justify-between mb-4 p-2.5 bg-white/50 rounded-lg border border-[#c8b89a]/50">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#2d1f0e] truncate">{authUser.full_name}</p>
                  <p className="text-xs text-[#8a7462] truncate">{authUser.email}</p>
                </div>
                <button onClick={signOut} title="Sign out" className="p-1.5 text-[#8a7462] hover:text-red-600 transition-colors flex-shrink-0">
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}
            <button
              onClick={createNewThread}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-900 text-white rounded-lg font-medium transition-colors shadow-sm"
            >
              <Plus className="w-5 h-5" /> New Consultation
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
            {threads.length === 0 ? (
              <div className="text-center text-[#8a7462] py-12 px-4">
                <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-40" />
                <p className="text-sm">No conversations yet</p>
              </div>
            ) : (
              threads.map(thread => (
                <div
                  key={thread.thread_id}
                  onClick={() => loadThread(thread.thread_id)}
                  className={`group p-3.5 rounded-lg cursor-pointer transition-all border ${currentThreadId === thread.thread_id
                    ? 'bg-white border-[#74603e]/50 shadow-sm'
                    : 'bg-transparent border-transparent hover:bg-white/60 hover:border-[#c8b89a]'
                    }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <FileText className="w-4 h-4 text-[#74603e] flex-shrink-0" />
                        <p className="text-[#2d1f0e] font-medium text-sm truncate">
                          {thread.title || 'New Case'}
                        </p>
                      </div>
                      <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs mb-1.5 border ${getStatusColor(thread.status)}`}>
                        {getStatusIcon(thread.status)}
                        <span>{getStatusText(thread.status)}</span>
                      </div>
                      <p className="text-[#8a7462] text-xs">{formatDate(thread.updated_at)}</p>
                    </div>
                    <button
                      onClick={e => deleteThread(thread.thread_id, e)}
                      className="ml-2 p-1.5 text-[#8a7462] hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Main chat area ───────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0">

          {/* Header */}
          <div className="bg-white border-b border-[#c8b89a] px-6 py-4 shadow-sm">
            <div className="flex items-center gap-4">
              <div className="p-2.5 bg-[#74603e]/10 rounded-xl border border-[#c8b89a]">
                <BookOpen className="w-5 h-5 text-[#74603e]" />
              </div>
              <div className="flex-1">
                <h2 className="text-[#2d1f0e] font-semibold text-base">AI Legal Consultation</h2>
                <p className="text-xs text-[#8a7462] mt-0.5">Transparent reasoning · Precedent analysis · Step-by-step guidance</p>
              </div>
              {currentThreadId && (
                <div className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 ${getStatusColor(conversationStatus)}`}>
                  {getStatusIcon(conversationStatus)}
                  {getStatusText(conversationStatus)}
                </div>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
            {error && (
              <div className="max-w-4xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-red-700 font-medium">Error</p>
                  <p className="text-red-600 text-sm mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {messages.length === 0 && !streamingMessage && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md px-4">
                  <div className="inline-flex p-5 bg-[#74603e]/10 rounded-2xl border border-[#c8b89a] mb-5">
                    <Scale className="w-14 h-14 text-[#74603e]" />
                  </div>
                  <h3 className="text-2xl font-bold text-[#2d1f0e] mb-2">Welcome to Your Legal Assistant</h3>
                  <p className="text-[#8a7462] text-sm leading-relaxed">
                    I'll provide transparent, explainable legal advice with clear reasoning and precedent analysis.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg, idx) => {
              const isGathering = msg.messageType === 'information_gathering';
              const nextMsg = messages[idx + 1];
              const showInfoAfter = isGathering && nextMsg?.messageType === 'final_response';
              const infoToDisplay = showInfoAfter ? (msg.infoCollected || infoCollected) : null;

              return (
                <React.Fragment key={idx}>
                  <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                    <div className="max-w-4xl w-full">
                      <div className={`rounded-2xl shadow-sm overflow-hidden border ${msg.role === 'user'
                        ? 'ml-auto max-w-2xl bg-amber-900 border-amber-950 text-white'
                        : msg.messageType === 'clarification'
                          ? 'bg-amber-50 border-amber-200 text-[#2d1f0e]'
                          : msg.messageType === 'information_gathering'
                            ? 'bg-[#f7f3ec] border-[#c8b89a] text-[#2d1f0e]'
                            : 'bg-white border-[rgba(116,96,62,0.20)] text-[#2d1f0e]'
                        }`}>
                        <div className="px-5 py-4">
                          {msg.messageType === 'clarification' && (
                            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-amber-200">
                              <AlertCircle className="w-4 h-4 text-amber-600" />
                              <span className="text-xs font-semibold text-amber-700 uppercase tracking-wide">Need Clarification</span>
                            </div>
                          )}
                          {msg.messageType === 'information_gathering' && (
                            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[#c8b89a]">
                              <Info className="w-4 h-4 text-[#74603e]" />
                              <span className="text-xs font-semibold text-[#74603e] uppercase tracking-wide">Gathering Information</span>
                            </div>
                          )}
                          <div
                            dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                            className={`prose max-w-none text-sm leading-relaxed ${msg.role === 'user' ? 'prose-invert' : ''}`}
                          />
                          {renderInfoProgress(msg)}
                        </div>
                        {msg.timestamp && (
                          <div className={`px-5 py-1.5 border-t ${msg.role === 'user' ? 'border-white/10 bg-black/10' : 'border-[rgba(116,96,62,0.10)] bg-[#f7f3ec]/50'}`}>
                            <p className={`text-xs ${msg.role === 'user' ? 'text-white/50' : 'text-[#8a7462]'}`}>{formatTime(msg.timestamp)}</p>
                          </div>
                        )}
                      </div>

                      {/* Reasoning */}
                      {msg.messageType === 'final_response' && msg.reasoningSteps && msg.reasoningSteps.length > 0 && (
                        <div className="mt-4 space-y-2.5">
                          <div className="flex items-center gap-2 mb-2">
                            <Brain className="w-5 h-5 text-[#74603e]" />
                            <h3 className="text-[#2d1f0e] font-semibold">How I Reached This Conclusion</h3>
                          </div>
                          {msg.reasoningSteps.map((step, i) => <ReasoningStepCard key={i} step={step} index={i} />)}
                        </div>
                      )}

                      {/* Precedents */}
                      {msg.messageType === 'final_response' && msg.precedentExplanations && msg.precedentExplanations.length > 0 && (
                        <div className="mt-4 space-y-2.5">
                          <div className="flex items-center gap-2 mb-2">
                            <Lightbulb className="w-5 h-5 text-[#74603e]" />
                            <h3 className="text-[#2d1f0e] font-semibold">Why These Precedents Matter</h3>
                          </div>
                          {msg.precedentExplanations.map((p, i) => <PrecedentCard key={i} precedent={p} index={i} />)}
                        </div>
                      )}
                    </div>
                  </div>

                  {showInfoAfter && infoToDisplay && Object.keys(infoToDisplay).length > 0 && (
                    <div className="animate-fade-in my-4 max-w-4xl">
                      <InfoCollectedSummary collectedInfo={infoToDisplay} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}

            {/* Streaming */}
            {streamingMessage && (
              <div className="flex justify-start animate-fade-in">
                <div className="max-w-3xl bg-white border border-[rgba(116,96,62,0.20)] rounded-2xl shadow-sm overflow-hidden">
                  <div className="px-5 py-4">
                    <div dangerouslySetInnerHTML={{ __html: formatMessage(streamingMessage) }} className="prose max-w-none text-[#2d1f0e] text-sm leading-relaxed" />
                    <div className="flex items-center gap-2 mt-3">
                      <Loader2 className="w-4 h-4 animate-spin text-[#74603e]" />
                      <span className="text-xs text-[#74603e]">Processing…</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Sources */}
            {sources.length > 0 && !streamingMessage && (
              <div className="max-w-3xl mx-auto bg-[#f7f3ec] border border-[#c8b89a] rounded-xl p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                  <BookOpen className="w-5 h-5 text-[#74603e]" />
                  <span className="text-sm font-semibold text-[#74603e]">Legal References</span>
                </div>
                <div className="space-y-2.5">
                  {sources.map((src, idx) => (
                    <div key={idx} className="bg-white rounded-lg p-3.5 border border-[rgba(116,96,62,0.15)] shadow-sm">
                      {src.url
                        ? <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-[#74603e] hover:text-[#5c4b2f] font-medium flex items-center gap-2">{src.title}<ExternalLink className="w-4 h-4" /></a>
                        : <span className="text-[#2d1f0e] font-medium">{src.title}</span>
                      }
                      {src.category && <span className="inline-block mt-2 px-2.5 py-0.5 bg-[#f0ebe1] text-[#74603e] text-xs rounded-full border border-[#c8b89a]">{src.category}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="bg-white border-t border-[#c8b89a] px-6 py-4 shadow-md">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-end gap-3">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyPress}
                  placeholder="Describe your legal situation…"
                  disabled={isLoading}
                  rows={1}
                  className="flex-1 px-4 py-3 bg-[#f7f3ec] border border-[#c8b89a] rounded-xl text-[#2d1f0e] placeholder-[#8a7462] resize-none disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#74603e]/40 focus:border-[#74603e] transition-colors text-sm"
                  style={{ minHeight: '48px', maxHeight: '120px' }}
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={isLoading || !input.trim()}
                  className="px-5 py-3 bg-amber-900 text-white rounded-xl transition-colors shadow-sm font-medium flex items-center gap-2 text-sm disabled:opacity-50"
                >
                  {isLoading
                    ? <><Loader2 className="w-4 h-4 animate-spin" /><span className="hidden sm:inline">Processing</span></>
                    : <><Send className="w-4 h-4" /><span className="hidden sm:inline">Send</span></>}
                </button>
              </div>
            </div>
          </div>
        </div>

        <style>{`
          @keyframes fade-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
          .animate-fade-in { animation: fade-in 0.25s ease-out; }
        `}</style>
      </div>
    </div>
  );
};

export default LegalAssistChat;