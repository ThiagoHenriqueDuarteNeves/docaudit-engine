import { Eraser, MessageSquare, Trash2, LogOut, Settings as SettingsIcon } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../UI/Button';
import { useSettings } from '../../store/settings';

interface SidebarProps {
    isOpen: boolean;
    onClose: () => void;
    onNewChat: () => void;
    // TODO: Add history props type
    history: any[];
    onSelectChat: (id: string) => void;
    onDeleteChat: (id: string) => void;
    activeChatId?: string;
    onLogout: () => void;
    username: string;
    onModelsClick?: () => void;
}

export function Sidebar({
    isOpen,
    onClose,
    onNewChat,
    history,
    onSelectChat,
    onDeleteChat,
    activeChatId,
    onLogout,
    username,
    onModelsClick
}: SidebarProps) {
    const { settings } = useSettings();

    const handleMobileClose = () => {
        // Close only on mobile
        if (!window.matchMedia("(min-width: 768px)").matches) {
            onClose();
        }
    };

    return (
        <>
            {/* Mobile Overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={onClose}
                />
            )}

            {/* Sidebar Container */}
            <aside className={cn(
                "fixed md:static inset-y-0 left-0 z-50 bg-gray-900 flex flex-col transition-all duration-300",
                isOpen ? "w-72 translate-x-0 border-r border-gray-800" : "w-72 -translate-x-full md:w-0 md:translate-x-0 md:border-none overflow-hidden"
            )}>

                {/* Header (New Chat) */}
                <div className="p-4 border-b border-gray-800 space-y-2">
                    <Button
                        onClick={() => {
                            onNewChat();
                            handleMobileClose();
                        }}
                        className="w-full gap-2 p-3 h-auto"
                    >
                        <Eraser size={20} />
                        Limpar Conversa
                    </Button>

                    <Button
                        onClick={() => {
                            if (onModelsClick) onModelsClick();
                            handleMobileClose();
                        }}
                        variant="secondary"
                        className="w-full gap-2 p-3 h-auto text-sm bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 font-medium"
                    >
                        <SettingsIcon size={16} />
                        Modelos
                    </Button>
                </div>

                {/* Chat History List */}
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {history.length === 0 ? (
                        <div className="text-center text-gray-500 mt-10 text-sm">
                            <p>Nenhuma conversa ainda.</p>
                        </div>
                    ) : (
                        history.map((chat) => (
                            <div
                                key={chat.id}
                                className={cn(
                                    "group flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors text-sm",
                                    activeChatId === chat.id
                                        ? "bg-gray-800 text-white"
                                        : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
                                )}
                                onClick={() => {
                                    onSelectChat(chat.id);
                                    handleMobileClose();
                                }}
                            >
                                <MessageSquare size={16} />
                                <span className="flex-1 truncate">
                                    {chat.title || "Nova Conversa"}
                                </span>

                                {/* Delete Button (visible on hover or active) */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDeleteChat(chat.id);
                                    }}
                                    className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity p-1"
                                    title="Excluir"
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        ))
                    )}
                </div>

                {/* Footer (User Profile) */}
                <div className="p-4 border-t border-gray-800">
                    {/* Active Model Indicator */}
                    {settings.selectedModel && (
                        <div className="mb-3 px-1">
                            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-0.5">
                                Modelo Ativo
                            </div>
                            <div className="text-xs text-blue-400 font-medium truncate" title={settings.selectedModel}>
                                {settings.selectedModel}
                            </div>
                        </div>
                    )}

                    <div className="flex items-center justify-between text-gray-400 text-sm">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold overflow-hidden border border-gray-700">
                                <img src="/aurora_avatar.png" alt="Aurora" className="w-full h-full object-cover" />
                            </div>
                            <span className="font-medium text-gray-200 truncate max-w-[120px]">
                                {username.split('-')[0]}
                            </span>
                        </div>

                        <button
                            onClick={onLogout}
                            className="p-2 hover:bg-gray-800 rounded-full transition-colors text-gray-500 hover:text-red-400"
                            title="Sair (Logout)"
                        >
                            <LogOut size={18} />
                        </button>
                    </div>
                    {/* Debug/Reset Link */}
                    <div className="mt-4 px-1">
                        <button
                            onClick={() => {
                                if (confirm('Resetar configuração do servidor?')) {
                                    localStorage.removeItem('lmstudio-settings');
                                    window.location.reload();
                                }
                            }}
                            className="w-full py-2.5 px-3 text-sm font-medium text-gray-400 hover:text-red-300 bg-gray-800/30 hover:bg-gray-800 border border-gray-700/50 hover:border-red-900/30 rounded-lg transition-all flex items-center justify-center gap-2"
                        >
                            Resetar Servidor
                        </button>
                    </div>
                </div>
            </aside>
        </>
    );
}
