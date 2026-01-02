/**
 * Componente MarkdownMessage - Renderiza mensagens com Markdown e syntax highlighting
 */

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import auroraAvatar from '../assets/aurora_avatar.png'

interface MarkdownMessageProps {
  content: string
  role: 'user' | 'assistant' | 'system'
}

export function MarkdownMessage({ content, role }: MarkdownMessageProps) {
  const [showThinking, setShowThinking] = useState(false)
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null)

  // Detecta se há tag <think> (completa ou incompleta)
  const hasThinking = /<think>/i.test(content)

  // Extrai todo o conteúdo dentro de <think>...</think> ou <think>...(até o fim se incompleto)
  let thinkingContent = ''
  let visibleContent = content

  if (hasThinking) {
    // Tenta pegar o conteúdo entre <think> e </think>
    const completeMatch = content.match(/<think>([\s\S]*?)<\/think>/i)
    if (completeMatch) {
      thinkingContent = completeMatch[1].trim()
      visibleContent = content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
    } else {
      // Se não tem </think>, pega tudo depois de <think>
      const incompleteMatch = content.match(/<think>([\s\S]*?)$/i)
      if (incompleteMatch) {
        thinkingContent = incompleteMatch[1].trim()
        visibleContent = content.replace(/<think>[\s\S]*$/gi, '').trim()
      }
    }
  }

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopyFeedback('✅')
      setTimeout(() => setCopyFeedback(null), 1500)
    } catch (err) {
      console.error('Falha ao copiar:', err)
      setCopyFeedback('❌')
    }
  }

  const handleCopyCode = async (text: string) => {
    try {
      if (!navigator.clipboard) throw new Error('Clipboard API indisponível')
      await navigator.clipboard.writeText(text)

      setCopyFeedback('code')
      setTimeout(() => setCopyFeedback(null), 1500)
    } catch (err) {
      console.error('Falha ao copiar código:', err)
      setCopyFeedback('❌')
      setTimeout(() => setCopyFeedback(null), 1500)
    }
  }

  return (
    <div className={`message message-${role}`}>
      <div className="message-avatar">
        {role === 'user' ? '👤' : (
          <img
            src={auroraAvatar}
            alt="Aurora"
            style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
          />
        )}
      </div>
      <div className="message-content">
        <div className="message-header">
          <span className="message-role">{role === 'user' ? 'Você' : 'Aurora'}</span>
          <div className="message-actions">
            {hasThinking && (
              <button
                className="btn-icon-small"
                onClick={() => setShowThinking(!showThinking)}
                title={showThinking ? 'Ocultar pensamento' : 'Mostrar pensamento'}
              >
                {showThinking ? '🧠' : '💭'}
              </button>
            )}
            <button
              className="btn-copy"
              onClick={handleCopyMessage}
              title="Copiar mensagem"
            >
              {copyFeedback || '📋'}
            </button>
          </div>
        </div>

        {/* Seção de pensamento (thinking) */}
        {hasThinking && showThinking && (
          <div className="message-thinking">
            <div className="thinking-header">
              <span>🧠 Raciocínio</span>
              <button
                className="btn-copy-small"
                onClick={() => handleCopyCode(thinkingContent)}
                title="Copiar raciocínio"
              >
                📋
              </button>
            </div>
            <div className="thinking-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {thinkingContent}
              </ReactMarkdown>
            </div>
          </div>
        )}

        <div className="message-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              pre({ children }) {
                // Tenta extrair props do elemento <code> filho
                const codeElement = children as any
                const className = codeElement?.props?.className || ''
                const codeContent = String(codeElement?.props?.children || '').replace(/\n$/, '')
                const match = /language-(\w+)/.exec(className || '')
                const lang = match ? match[1] : ''

                // Se não tiver info de código válido, renderiza pre normal
                if (!codeContent) {
                  return <pre>{children}</pre>
                }

                // Se for um bloco de código válido
                return (
                  <div className="code-block" style={{ position: 'relative', marginTop: '1rem', marginBottom: '1rem' }}>
                    <div className="code-header" style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: '#1f2937',
                      padding: '0.5rem 1rem',
                      borderTopLeftRadius: '0.5rem',
                      borderTopRightRadius: '0.5rem',
                      borderBottom: '1px solid #374151'
                    }}>
                      <span className="code-lang" style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 'bold' }}>
                        {lang || 'Text'}
                      </span>
                      <button
                        onClick={() => handleCopyCode(codeContent)}
                        className="btn-copy-code"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          fontSize: '0.75rem',
                          color: '#d1d5db',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer'
                        }}
                      >
                        <span>{copyFeedback === 'code' ? '✅' : '📋'}</span>
                        <span>{copyFeedback === 'code' ? 'Copiado!' : 'Copiar'}</span>
                      </button>
                    </div>

                    <div style={{ borderRadius: '0 0 0.5rem 0.5rem', overflow: 'hidden' }}>
                      <SyntaxHighlighter
                        children={codeContent}
                        style={vscDarkPlus}
                        language={lang}
                        PreTag="div"
                        customStyle={{ margin: 0, padding: '1rem', overflowX: 'auto' }}
                      />
                    </div>
                  </div>
                )
              },
              code({ inline, className, children, ...props }: any) {
                // Código inline simples (backticks únicos)
                if (inline) {
                  return (
                    <code className={className} {...props} style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.4rem', borderRadius: '4px', fontFamily: 'monospace' }}>
                      {children}
                    </code>
                  )
                }
                // Se chegar aqui, é porque o 'pre' override não pegou, ou é algo aninhado diferente.
                // Retorna o código cru como fallback
                return <code className={className} {...props}>{children}</code>
              },
              table({ children, ...props }) {
                return (
                  <div className="table-wrapper">
                    <table {...props}>{children}</table>
                  </div>
                )
              },
            }}
          >
            {visibleContent}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
