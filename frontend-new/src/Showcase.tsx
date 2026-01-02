import { useState } from 'react';
import { MainLayout } from './components/Layout/MainLayout';
import { MessageBubble } from './components/Chat/MessageBubble';
import { ChatInput } from './components/Chat/ChatInput';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    image?: string;
}

export function Showcase() {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: 'Olá! Sou a Aurora AI. Como posso ajudar com seus documentos hoje?' },
        { role: 'user', content: 'Você consegue ler arquivos PDF?' },
        { role: 'assistant', content: 'Sim! **Eu consigo ler PDFs, arquivos de texto e muito mais.** \n\nBasta anexar seu arquivo e eu farei uma análise completa para você. 📄✨' }
    ]);

    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSend = () => {
        if (!input.trim()) return;
        setMessages(prev => [...prev, { role: 'user', content: input }]);
        setInput('');
        setIsLoading(true);

        // Simulate thinking
        setTimeout(() => {
            setMessages(prev => [...prev, { role: 'assistant', content: 'Esta é uma resposta simulada para testar o **novo design**. O que achou? 🎨' }]);
            setIsLoading(false);
        }, 1500);
    };

    return (
        <MainLayout
            sidebarProps={{
                isOpen: true,
                onClose: () => { },
                onNewChat: () => alert('Novo Chat Clicked'),
                history: [
                    { id: '1', title: 'Análise de Contrato' },
                    { id: '2', title: 'Ideias de Marketing' },
                    { id: '3', title: 'Receita de Bolo' }
                ],
                username: 'Thiago',
                activeChatId: '1',
                onSelectChat: () => { },
                onDeleteChat: () => { },
                onLogout: () => { }
            }}
        >
            <div className="flex-1 overflow-y-auto">
                <div className="max-w-4xl mx-auto w-full pb-32">
                    {messages.map((m, i) => (
                        <MessageBubble
                            key={i}
                            role={m.role as any}
                            content={m.content}
                            image={m.image}
                        />
                    ))}
                    {isLoading && (
                        <div className="flex gap-4 px-4 py-6 bg-gray-900/50">
                            <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center animate-pulse">
                                ✨
                            </div>
                            <div className="flex items-center text-gray-400 text-sm">
                                Digitando...
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent pt-10 pb-6 px-4">
                <ChatInput value={input} onChange={setInput} onSend={handleSend} isLoading={isLoading} />
            </div>
        </MainLayout>
    );
}

