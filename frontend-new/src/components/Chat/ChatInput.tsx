import React, { useRef, useEffect } from 'react';
import { Send, Paperclip, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../UI/Button';

interface ChatInputProps {
    value: string;
    onChange: (value: string) => void;
    onSend: () => void;
    isLoading?: boolean;
    onImageSelect?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    selectedImage?: string | null;
    onClearImage?: () => void;
}

export function ChatInput({
    value,
    onChange,
    onSend,
    isLoading,
    onImageSelect,
    selectedImage,
    onClearImage
}: ChatInputProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'; // Reset
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [value]);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if ((!value.trim() && !selectedImage) || isLoading) return;

        onSend();

        // Reset height
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="w-full max-w-4xl mx-auto p-4">
            {/* Image Preview Container */}
            {selectedImage && (
                <div className="mb-4 relative inline-block">
                    <img
                        src={selectedImage}
                        alt="Preview"
                        className="h-20 w-auto rounded-lg border border-gray-700 shadow-lg object-cover"
                    />
                    <button
                        onClick={onClearImage}
                        className="absolute -top-2 -right-2 bg-gray-800 rounded-full p-1 text-gray-400 hover:text-white border border-gray-700 shadow-sm"
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            {/* Input Bar */}
            <div className="relative flex items-end gap-2 bg-gray-900 border border-gray-700 rounded-xl p-2 shadow-xl focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500 transition-all">
                {/* Upload Button */}
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={onImageSelect}
                    accept="image/*"
                    className="hidden"
                />
                <button
                    onClick={() => fileInputRef.current?.click()}
                    className="p-3 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
                    title="Anexar imagem"
                >
                    <Paperclip size={20} />
                </button>

                {/* Text Area */}
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Envie uma mensagem..."
                    className="flex-1 bg-transparent border-none outline-none focus:ring-0 focus:outline-none text-gray-100 placeholder-gray-500 resize-none py-3 max-h-[200px] min-h-[24px]"
                    rows={1}
                />

                {/* Send Button */}
                <Button
                    onClick={() => handleSubmit()}
                    disabled={(!value.trim() && !selectedImage) || isLoading}
                    className={cn(
                        "p-3 rounded-lg transition-all",
                        value.trim() || selectedImage
                            ? "bg-blue-600 text-white hover:bg-blue-700"
                            : "bg-gray-800 text-gray-500 cursor-not-allowed"
                    )}
                >
                    <Send size={18} />
                </Button>
            </div>
        </div>
    );
}
