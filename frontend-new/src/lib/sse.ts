/**
 * Utilitário para parse de Server-Sent Events (SSE)
 * Converte ReadableStream de texto em eventos SSE parseados
 */

export interface SSEMessage {
  event?: string
  data: string
  id?: string
  retry?: number
}

/**
 * Parse de uma linha SSE individual
 * Formato: "field: value" ou "data: {...}"
 */
function parseSSELine(line: string): Partial<SSEMessage> | null {
  if (!line || line.startsWith(':')) {
    return null // Comentário ou linha vazia
  }

  const colonIndex = line.indexOf(':')
  if (colonIndex === -1) {
    return null
  }

  const field = line.slice(0, colonIndex)
  let value = line.slice(colonIndex + 1)

  // Remove espaço inicial opcional após ':'
  if (value.startsWith(' ')) {
    value = value.slice(1)
  }

  return { [field]: value }
}

/**
 * Async generator que consome um ReadableStream e emite eventos SSE parseados
 * Trata corretamente linhas quebradas, buffering e [DONE]
 */
export async function* parseSSEStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<SSEMessage> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        break
      }

      // Decodifica chunk e adiciona ao buffer
      buffer += decoder.decode(value, { stream: true })

      // Processa linhas completas
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Mantém última linha incompleta no buffer

      let currentMessage: Partial<SSEMessage> = {}

      for (const line of lines) {
        const trimmedLine = line.trim()

        // Linha vazia = fim de mensagem
        if (!trimmedLine) {
          if (currentMessage.data) {
            // Verifica se é o marcador de fim [DONE]
            if (currentMessage.data === '[DONE]') {
              return // Finaliza o generator
            }

            yield currentMessage as SSEMessage
          }
          currentMessage = {}
          continue
        }

        // Parse da linha e merge no currentMessage
        const parsed = parseSSELine(trimmedLine)
        if (parsed) {
          Object.assign(currentMessage, parsed)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * Converte stream SSE em stream de objetos JSON parseados
 * Usado especificamente para chat completions do LM Studio
 */
export async function* streamChatCompletions<T = unknown>(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<T> {
  for await (const message of parseSSEStream(stream)) {
    try {
      const parsed = JSON.parse(message.data)
      yield parsed as T
    } catch (error) {
      console.warn('Falha ao parsear JSON do SSE:', message.data, error)
    }
  }
}
