import { useState, useRef, useEffect, useCallback } from 'react';
import { useSettings } from '../store/settings';
import { chatStream } from '../api/fastapi';
import type { ChatMessage } from '../types';

export interface UseChatReturn {
    messages: ChatMessage[];
    input: string;
    setInput: (value: string) => void;
    isStreaming: boolean;
    error: string | null;
    sendMessage: () => Promise<void>;
    stopGeneration: () => void;
    clearChat: () => void;
    selectedImage: string | null;
    selectedFile: File | null;
    handleImageSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
    removeImage: () => void;
    usage: { prompt: number; completion: number } | null;
}

export function useChat(userId: string): UseChatReturn {
    const { settings } = useSettings();
    const STORAGE_KEY = `chat_storage_v1_${userId}`;

    const [messages, setMessages] = useState<ChatMessage[]>(() => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            return saved ? JSON.parse(saved).messages : [];
        } catch (e) {
            console.error('Erro ao carregar histórico:', e);
            return [];
        }
    });

    const [input, setInput] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [usage, setUsage] = useState<{ prompt: number; completion: number } | null>(null);

    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const abortControllerRef = useRef<AbortController | null>(null);

    // Persist to localStorage
    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ messages, usage }));
        } catch (e) {
            console.error('Erro ao salvar histórico:', e);
        }
    }, [messages, usage, STORAGE_KEY]);

    const handleImageSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            if (file.size > 10 * 1024 * 1024) {
                alert("Imagem muito grande! Máximo 10MB.");
                return;
            }
            setSelectedFile(file);
            const reader = new FileReader();
            reader.onloadend = () => setSelectedImage(reader.result as string);
            reader.readAsDataURL(file);
        }
    }, []);

    const removeImage = useCallback(() => {
        setSelectedImage(null);
        setSelectedFile(null);
    }, []);

    const sendMessage = async () => {
        if ((!input.trim() && !selectedImage) || isStreaming) return;

        if (!settings.selectedModel) {
            setError('Selecione um modelo primeiro na barra lateral.');
            return;
        }

        const displayContent = selectedImage
            ? `${input.trim()}\n\n![Imagem anexada](${selectedImage})`
            : input.trim();

        const apiContent = input.trim() || (selectedImage ? '[Usuário enviou uma imagem]' : '');

        const displayMessage: ChatMessage = { role: 'user', content: displayContent };
        const apiMessage: ChatMessage = { role: 'user', content: apiContent };

        const newMessages = [...messages, displayMessage];
        setMessages(newMessages);
        setInput('');
        const imageToSend = selectedFile;
        removeImage();
        setError(null);
        setIsStreaming(true);

        const historyForApi = messages.map(m => ({
            role: m.role,
            content: m.role === 'user' ?
                (m.content.includes('![Imagem anexada]') ? m.content.split('\n\n![Imagem anexada]')[0] || '[Usuário enviou uma imagem]' : m.content)
                : m.content
        }));

        const apiMessages: ChatMessage[] = settings.systemPrompt
            ? [{ role: 'system', content: settings.systemPrompt }, ...historyForApi, apiMessage]
            : [...historyForApi, apiMessage];

        // Placeholder for assistant response
        setMessages([...newMessages, { role: 'assistant', content: '' }]);

        abortControllerRef.current = new AbortController();

        try {
            const stream = chatStream(
                settings.baseUrl,
                settings.apiKey,
                {
                    model: settings.selectedModel,
                    messages: apiMessages,
                    temperature: settings.temperature,
                    max_tokens: settings.maxTokens,
                    stream: true,
                    // @ts-ignore
                    image: imageToSend
                },
                abortControllerRef.current,
                settings.backendType
            );

            let accumulatedContent = '';

            for await (const chunk of stream) {
                const delta = chunk.choices[0]?.delta?.content;
                if (delta) {
                    accumulatedContent += delta;
                    setMessages((prev) => {
                        const updated = [...prev];
                        updated[updated.length - 1] = {
                            role: 'assistant',
                            content: accumulatedContent,
                        };
                        return updated;
                    });
                }
                if ((chunk as any).usage) {
                    setUsage({
                        prompt: (chunk as any).usage.prompt_tokens,
                        completion: (chunk as any).usage.completion_tokens,
                    });
                }
            }
        } catch (err: any) {
            setError(err.message || 'Erro desconhecido');
            setMessages((prev) => prev.slice(0, -1)); // Remove failed message
        } finally {
            setIsStreaming(false);
            abortControllerRef.current = null;

            // Cleanup base64 from history to save memory
            setMessages((prev) =>
                prev.map((m) => {
                    if (m.role === 'user' && m.content.includes('![Imagem anexada](data:')) {
                        const textOnly = m.content.split('\n\n![Imagem anexada]')[0] || '';
                        return {
                            ...m,
                            content: textOnly ? `${textOnly}\n\n[📷 Imagem enviada]` : '[📷 Imagem enviada]'
                        };
                    }
                    return m;
                })
            );
        }
    };

    const stopGeneration = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setIsStreaming(false);
        }
    }, []);

    const clearChat = useCallback(() => {
        setMessages([]);
        setUsage(null);
        localStorage.removeItem(STORAGE_KEY);
        setError(null);
    }, [STORAGE_KEY]);

    return {
        messages,
        input,
        setInput,
        isStreaming,
        error,
        sendMessage,
        stopGeneration,
        clearChat,
        selectedImage,
        selectedFile,
        handleImageSelect,
        removeImage,
        usage
    };
}
