
/**
 * Componente Chat - Interface principal de conversação
 */

import { useState, useRef, useEffect } from 'react'
import { useSettings } from '../store/settings'
import { chatStream, FastAPIError } from '../api/fastapi'
import { MarkdownMessage } from './MarkdownMessage'
import type { ChatMessage } from '../types'

export function Chat({ userId }: { userId: string }) {
  const { settings } = useSettings()
  const STORAGE_KEY = `chat_storage_v1_${userId}`

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved).messages : []
    } catch (e) {
      console.error('Erro ao carregar histórico:', e)
      return []
    }
  })
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [usage, setUsage] = useState<{ prompt: number; completion: number } | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved).usage : null
    } catch (e) {
      return null
    }
  })

  // Recarregar estado quando userId mudar (caso o componente não seja remontado)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        setMessages(parsed.messages || [])
        setUsage(parsed.usage || null)
      } else {
        setMessages([])
        setUsage(null)
      }
    } catch (e) {
      console.error('Erro ao carregar histórico:', e)
      setMessages([])
      setUsage(null)
    }
  }, [STORAGE_KEY])

  // Persistir mudanças no localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ messages, usage }))
    } catch (e) {
      console.error('Erro ao salvar histórico:', e)
    }
  }, [messages, usage])

  const abortControllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const autoScrollTimeoutRef = useRef<number | null>(null)

  // Auto-scroll inteligente: para quando usuário scrolla manualmente
  useEffect(() => {
    const container = chatContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50 // Margem de 50px

      if (isAtBottom) {
        // Usuário está no fundo, ativa auto-scroll
        if (!autoScroll) {
          setAutoScroll(true)
        }
        // Limpa timeout anterior se existir
        if (autoScrollTimeoutRef.current) {
          clearTimeout(autoScrollTimeoutRef.current)
        }
      } else {
        // Usuário scrollou para cima, desativa auto-scroll
        if (autoScroll) {
          setAutoScroll(false)
        }        // Se usuário voltar ao fundo por 1 segundo, reativa auto-scroll
        if (autoScrollTimeoutRef.current) {
          clearTimeout(autoScrollTimeoutRef.current)
        }
        autoScrollTimeoutRef.current = window.setTimeout(() => {
          const { scrollTop, scrollHeight, clientHeight } = container
          const stillAtBottom = scrollHeight - scrollTop - clientHeight < 50
          if (stillAtBottom) {
            setAutoScroll(true)
          }
        }, 1000)
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => {
      container.removeEventListener('scroll', handleScroll)
      if (autoScrollTimeoutRef.current) {
        clearTimeout(autoScrollTimeoutRef.current)
      }
    }
  }, [autoScroll])

  // Auto-scroll apenas se habilitado
  useEffect(() => {
    if (autoScroll) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, autoScroll])

  /* Image Upload Logic */
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 10 * 1024 * 1024) { // 10MB limit (increased)
        alert("Imagem muito grande! Máximo 10MB.")
        return
      }
      setSelectedFile(file) // Store file for upload

      const reader = new FileReader()
      reader.onloadend = () => {
        setSelectedImage(reader.result as string) // Store base64 for preview
      }
      reader.readAsDataURL(file)
    }
  }

  const handleSend = async () => {
    if ((!input.trim() && !selectedImage) || isStreaming) return

    if (!settings.selectedModel) {
      setError('Selecione um modelo primeiro')
      return
    }

    // Adiciona mensagem do usuário
    // displayContent: para exibição na UI (inclui Base64 para preview)
    // apiContent: para envio à API (texto puro, imagem vai separada via FormData)
    const displayContent = selectedImage
      ? `${input.trim()}\n\n![Imagem anexada](${selectedImage})`
      : input.trim()

    // API recebe apenas o texto - imagem vai como File separado no FormData
    const apiContent = input.trim() || (selectedImage ? '[Usuário enviou uma imagem]' : '')

    const displayMessage: ChatMessage = { role: 'user', content: displayContent }
    const apiMessage: ChatMessage = { role: 'user', content: apiContent }

    // UI recebe displayMessage (com preview da imagem)
    const newMessages = [...messages, displayMessage]
    setMessages(newMessages)
    setInput('')
    const imageToSend = selectedFile // Send the File object, not the base64 string
    setSelectedImage(null) // Limpar preview
    setSelectedFile(null) // Clear file
    if (fileInputRef.current) fileInputRef.current.value = '' // Reset input para permitir selecionar o mesmo arquivo
    setError(null)
    setIsStreaming(true)

    // Prepara mensagens para envio - usa apiMessage sem Base64
    // Substitui última mensagem por apiMessage (texto puro)
    const historyForApi = messages.map(m => ({
      role: m.role, content: m.role === 'user' ?
        (m.content.includes('![Imagem anexada]') ? m.content.split('\n\n![Imagem anexada]')[0] || '[Usuário enviou uma imagem]' : m.content)
        : m.content
    }))
    const apiMessages: ChatMessage[] = settings.systemPrompt
      ? [{ role: 'system', content: settings.systemPrompt }, ...historyForApi, apiMessage]
      : [...historyForApi, apiMessage]

    // Cria placeholder para resposta do assistente
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: 'Digitando...',
    }
    setMessages([...newMessages, assistantMessage])

    abortControllerRef.current = new AbortController()

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
          // @ts-ignore - Propriedade customizada injetada no chatStream
          image: imageToSend
        } as any,
        abortControllerRef.current
      )


      let accumulatedContent = ''

      for await (const chunk of stream) {
        // Extrai conteúdo do delta
        const delta = chunk.choices[0]?.delta?.content
        if (delta) {
          accumulatedContent += delta

          // Atualiza mensagem do assistente incrementalmente
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'assistant',
              content: accumulatedContent,
            }
            return updated
          })
        }

        // Captura usage se disponível (geralmente no último chunk)
        if ((chunk as any).usage) {
          setUsage({
            prompt: (chunk as any).usage.prompt_tokens,
            completion: (chunk as any).usage.completion_tokens,
          })
        }
      }
    } catch (err) {
      if (err instanceof FastAPIError) {
        setError(err.message)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Erro desconhecido durante o chat')
      }

      // Remove mensagem do assistente se houve erro
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null

      // OTIMIZAÇÃO CRÍTICA: Limpar Base64 do histórico para não travar o navegador
      setMessages((prev) =>
        prev.map((m) => {
          if (m.role === 'user' && m.content.includes('![Imagem anexada](data:')) {
            const textOnly = m.content.split('\n\n![Imagem anexada]')[0] || ''
            return {
              ...m,
              content: textOnly ? `${textOnly}\n\n[📷 Imagem enviada]` : '[📷 Imagem enviada]'
            }
          }
          return m
        })
      )
    }
  }

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsStreaming(false)
    }
  }

  const handleClear = () => {
    setMessages([])
    setUsage(null)
    localStorage.removeItem(STORAGE_KEY)
    setError(null)
  }

  const handleResend = () => {
    if (messages.length >= 2) {
      // Pega última mensagem do usuário
      const lastUserMessage = [...messages]
        .reverse()
        .find((m) => m.role === 'user')

      if (lastUserMessage) {
        // Remove última troca (user + assistant)
        const withoutLast = messages.slice(0, -2)
        setMessages(withoutLast)
        setInput(lastUserMessage.content)
      }
    }
  }

  // Enter envia, Shift+Enter quebra linha
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  return (
    <main className="chat-container">
      <div className="chat-messages" ref={chatContainerRef}>
        {messages.length === 0 ? (
          <div className="empty-chat">
            <h2>👋 Bem-vindo!</h2>
            <p>Selecione um modelo e comece a conversar</p>
          </div>
        ) : (
          messages.map((msg, idx) => <MarkdownMessage key={idx} content={msg.content} role={msg.role} />)
        )}

        {/* Streaming indicator removed to avoid duplication */}

        <div ref={messagesEndRef} />
      </div>



      {error && (
        <div className="chat-error">
          ❌ <strong>Erro:</strong> {error}
        </div>
      )}

      <div className="chat-footer">
        {usage && (
          <div className="chat-stats">
            📊 Tokens: {usage.prompt} prompt + {usage.completion} completion ={' '}
            {usage.prompt + usage.completion} total
          </div>
        )}

        <div className="chat-actions">
          {messages.length > 0 && (
            <>
              <button onClick={handleClear} disabled={isStreaming} className="btn-secondary">
                🗑️ Limpar
              </button>
              <button onClick={handleResend} disabled={isStreaming || messages.length < 2} className="btn-secondary">
                🔄 Reenviar
              </button>
            </>
          )}
          {isStreaming && (
            <button onClick={handleStop} className="btn-danger">
              ⏹️ Parar
            </button>
          )}
        </div>

        <div className="chat-input-wrapper" style={{ flexDirection: 'column' }}>
          {/* Image Preview */}
          {selectedImage && (
            <div className="image-preview" style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '5px 10px',
              background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '5px', alignSelf: 'flex-start'
            }}>
              <img src={selectedImage} alt="Preview" style={{ height: '40px', borderRadius: '4px' }} />
              <button onClick={() => { setSelectedImage(null); setSelectedFile(null); }} style={{ background: 'none', border: 'none', color: '#ff6b6b', cursor: 'pointer' }}>✖</button>
            </div>
          )}

          <div style={{ display: 'flex', width: '100%', alignItems: 'flex-end', gap: '0.5rem' }}>
            <button
              className="btn-attach"
              onClick={() => fileInputRef.current?.click()}
              title="Anexar Imagem"
              style={{ padding: '0.5rem', fontSize: '1.2rem', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
            >
              📎
            </button>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept="image/*"
              onChange={handleImageSelect}
            />

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Digite sua mensagem... (Enter para enviar, Shift+Enter para quebrar linha)"
              disabled={isStreaming}
              rows={1} // Auto-grow handled by CSS usually, but keeping simple
              style={{ flex: 1 }}
            />
            <button
              onClick={handleSend}
              disabled={(!input.trim() && !selectedImage) || isStreaming || !settings.selectedModel}
              className="btn-send"
            >
              📤
            </button>
          </div>
        </div>

        <small className="chat-hint">
          Modelo: <strong>{settings.selectedModel || 'Nenhum selecionado'}</strong> | Temp:{' '}
          {settings.temperature}
        </small>
      </div>
    </main>
  )
}
