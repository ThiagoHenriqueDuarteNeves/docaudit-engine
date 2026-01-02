import { useState, useEffect, useRef } from 'react'
import { SettingsProvider, useSettings } from './store/settings'
import { MainLayout } from './components/Layout/MainLayout'
import { ServerSetup } from './components/ServerSetup'
import { LoginOverlay } from './components/LoginOverlay'
import { DocumentsTab } from './components/DocumentsTab'
import { ContextDebug } from './components/ContextDebug'
import { ChatInput } from './components/Chat/ChatInput'
import { MessageBubble } from './components/Chat/MessageBubble'
import { useChat } from './hooks/useChat'
import { ModelSelect } from './components/ModelSelect'


interface ChatViewProps {
  chat: ReturnType<typeof useChat>;
  userId: string;
}

function ChatView({ chat, userId }: ChatViewProps) {
  const {
    messages,
    input,
    setInput,
    isStreaming,
    error,
    sendMessage,
    selectedImage,
    handleImageSelect,
    removeImage
  } = chat;

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  return (
    <>
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full pb-48 pt-8 px-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-20">
              <h2 className="text-2xl font-bold mb-2 text-gray-300">Olá, {userId.split('-')[0]}!</h2>
              <p>Inicie uma conversa para começar.</p>
            </div>
          )}

          {messages.map((m, i) => (
            <MessageBubble
              key={i}
              role={m.role as any}
              content={m.content}
            />
          ))}

          {error && (
            <div className="p-4 mb-4 text-red-400 bg-red-900/20 border border-red-900 rounded-lg mx-auto max-w-2xl">
              ❌ {error}
            </div>
          )}

          {isStreaming && (
            <div className="flex gap-4 px-4 py-6 bg-gray-900/50">
              <div className="w-8 h-8 rounded-full flex items-center justify-center animate-pulse border border-gray-700 overflow-hidden">
                <img src="/aurora_avatar.png" className="w-full h-full object-cover" />
              </div>
              <div className="flex items-center text-gray-400 text-sm">
                Digitando...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent pt-10 pb-6 px-4 z-10">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={sendMessage}
          isLoading={isStreaming}
          onImageSelect={handleImageSelect}
          selectedImage={selectedImage}
          onClearImage={removeImage}
        />
      </div>
    </>
  )
}

function AppContent() {
  const { settings } = useSettings()
  const [activeTab, setActiveTab] = useState<'chat' | 'documents' | 'debug'>('chat')
  const [userId, setUserId] = useState<string | null>(localStorage.getItem('chat_user_id'))
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isModelSelectOpen, setIsModelSelectOpen] = useState(false)

  // Initialize sidebar state based on screen size
  useEffect(() => {
    if (window.matchMedia("(min-width: 768px)").matches) {
      setIsSidebarOpen(true)
    }
  }, [])

  // Sync user from localStorage
  useEffect(() => {
    const storedUser = localStorage.getItem('chat_user_id')
    if (storedUser) setUserId(storedUser)
  }, [])

  const handleLogin = (name: string) => {
    localStorage.setItem('chat_user_id', name)
    setUserId(name)
    // Close sidebar on mobile after login
    if (!window.matchMedia("(min-width: 768px)").matches) {
      setIsSidebarOpen(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('chat_user_id')
    setUserId(null)
  }

  // Hoist chat state here so we can pass clearChat to layout
  // Only call useChat if we have a userId to avoid errors/hooks violations if it depends on it
  // But hooks must be consistent. We'll pass "" if null, assuming useChat handles empty user safely or we only render if userId.
  const chat = useChat(userId || "guest");

  if (!userId) {
    return <LoginOverlay onLogin={handleLogin} />
  }

  if (!settings.serverConfigured) {
    return <ServerSetup />
  }

  return (
    <>
      <MainLayout
        sidebarProps={{
          isOpen: isSidebarOpen,
          onClose: () => setIsSidebarOpen(false),
          onNewChat: chat.clearChat,
          history: [], // TODO: Load history
          username: userId,
          activeChatId: '1',
          onSelectChat: (id) => console.log('Select', id),
          onDeleteChat: (id) => console.log('Delete', id),
          onLogout: handleLogout,
          onModelsClick: () => setIsModelSelectOpen(true)
        }}
      >

        {/* Mobile Header */}
        <div className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between">
          {/* Hamburger Menu (Mobile Only) */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 rounded-lg bg-gray-800/80 text-gray-300 hover:bg-gray-700 transition-colors"
            aria-label="Menu"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>

          {/* Tab Buttons */}
          <div className="flex gap-2 ml-auto">
            <button onClick={() => setActiveTab('chat')} className={`px-3 py-1 rounded text-sm transition-colors ${activeTab === 'chat' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'bg-gray-800/50 text-gray-400 hover:bg-gray-800'}`}>Chat</button>
            <button onClick={() => setActiveTab('documents')} className={`px-3 py-1 rounded text-sm transition-colors ${activeTab === 'documents' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'bg-gray-800/50 text-gray-400 hover:bg-gray-800'}`}>Docs</button>
            <button onClick={() => setActiveTab('debug')} className={`px-3 py-1 rounded text-sm transition-colors ${activeTab === 'debug' ? 'bg-red-900/30 text-red-400 border border-red-900/50' : 'bg-gray-800/50 text-red-400/50 hover:bg-gray-800'}`}>Debug</button>
          </div>
        </div>

        {activeTab === 'chat' && <ChatView chat={chat} userId={userId} />}
        {activeTab === 'documents' && (
          <div className="p-8 h-full overflow-y-auto bg-gray-950 text-white">
            <DocumentsTab />
          </div>
        )}
        {activeTab === 'debug' && (
          <div className="p-8 h-full overflow-y-auto bg-gray-950 text-white">
            <ContextDebug />
          </div>
        )}

      </MainLayout>

      {/* Generic Modal Wrapper for Model Select */}
      {isModelSelectOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-2 sm:p-4">
          <div className="bg-gray-900 rounded-2xl w-full sm:max-w-md h-[90vh] sm:h-auto sm:max-h-[80vh] overflow-hidden border border-gray-800 shadow-2xl relative flex flex-col">
            <ModelSelect isOpen={true} onClose={() => setIsModelSelectOpen(false)} />
          </div>
        </div>
      )}
    </>
  )
}

function App() {
  return (
    <SettingsProvider>
      <AppContent />
    </SettingsProvider>
  )
}

export default App
