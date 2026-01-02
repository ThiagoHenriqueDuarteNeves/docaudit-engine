import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { User, Copy, Check } from 'lucide-react';
import { cn } from '../../lib/utils';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    image?: string; // Base64 or URL
    timestamp?: string;
}

// Helper Component for Code Blocks with Copy Button
const CodeBlock = ({ language, children, ...props }: any) => {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(String(children));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group rounded-md border border-gray-800 bg-gray-950 my-4">
            {/* Header / Language Badge and Copy Button */}
            <div className="flex items-center justify-between px-4 py-2 bg-gray-900/50 border-b border-gray-800 rounded-t-md">
                <span className="text-xs font-mono text-gray-400 lowercase">{language || 'text'}</span>
                <button
                    onClick={handleCopy}
                    className="p-1 hover:bg-gray-800 rounded transition-colors text-gray-400 hover:text-white"
                    title="Copiar código"
                >
                    {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                </button>
            </div>

            {/* Syntax Highlighter */}
            <SyntaxHighlighter
                {...props}
                children={String(children).replace(/\n$/, '')}
                style={vscDarkPlus}
                language={language}
                PreTag="div"
                className="!bg-transparent !p-4 !m-0 !border-none overflow-x-auto"
                customStyle={{ margin: 0, background: 'transparent' }}
            />
        </div>
    );
};

export function MessageBubble({ role, content, image, timestamp }: MessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <div className={cn(
            "flex w-full gap-4 px-4 py-6",
            isUser ? "bg-transparent" : "bg-gray-900/50 border-y border-gray-800/50"
        )}>
            {/* Avatar */}
            <div className={cn(
                "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center overflow-hidden border border-gray-700",
                isUser ? "bg-blue-600 text-white" : "bg-transparent"
            )}>
                {isUser ? <User size={18} /> : (
                    <img src="/aurora_avatar.png" alt="Aurora" className="w-full h-full object-cover" />
                )}
            </div>

            {/* Content */}
            <div className="flex-1 space-y-2 overflow-hidden">
                <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-200">
                        {isUser ? "Você" : "Aurora AI"}
                    </span>
                    {timestamp && (
                        <span className="text-xs text-gray-500">{timestamp}</span>
                    )}
                </div>

                {/* Image Attachment */}
                {image && (
                    <div className="mb-2">
                        <img
                            src={image}
                            alt="Attachment"
                            className="max-w-xs md:max-w-md rounded-lg border border-gray-700 shadow-lg"
                        />
                    </div>
                )}

                {/* Markdown Text */}
                <div className="prose prose-invert prose-p:leading-relaxed prose-pre:p-0 max-w-none text-gray-300">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                            code({ node, className, children, ...props }) {
                                const match = /language-(\w+)/.exec(className || '')
                                return match ? (
                                    <CodeBlock
                                        language={match[1]}
                                        children={children}
                                        {...props}
                                    />
                                ) : (
                                    <code {...props} className={cn("bg-gray-800 px-1 py-0.5 rounded text-sm text-pink-300", className)}>
                                        {children}
                                    </code>
                                )
                            }
                        }}
                    >
                        {content}
                    </ReactMarkdown>
                </div>
            </div>
        </div>
    );
}
