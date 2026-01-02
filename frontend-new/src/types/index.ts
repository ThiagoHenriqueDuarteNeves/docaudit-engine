// Tipos para a API do LM Studio (OpenAI-compatible)

export interface Model {
  id: string
  object: 'model'
  created?: number
  owned_by?: string
}

export interface ModelsResponse {
  object: 'list'
  data: Model[]
  current?: string
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatCompletionRequest {
  model: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
  stream?: boolean
}

export interface ChatCompletionChunk {
  id: string
  object: 'chat.completion.chunk'
  created: number
  model: string
  choices: Array<{
    index: number
    delta: {
      role?: string
      content?: string
    }
    finish_reason: string | null
  }>
}

export interface ChatCompletionResponse {
  id: string
  object: 'chat.completion'
  created: number
  model: string
  choices: Array<{
    index: number
    message: ChatMessage
    finish_reason: string
  }>
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export interface AppSettings {
  baseUrl: string
  apiKey: string
  selectedModel: string
  temperature: number
  maxTokens: number
  contextWindow: number
  systemPrompt: string
  modelPrefixFilter: string
  serverConfigured: boolean
  backendType?: 'fastapi' | 'openai'
}

export interface DebugSnippet {
  source: string
  text: string
  score?: number
  metadata?: Record<string, any>
}

export interface DebugResponse {
  formatted_prompt: string
  mem_hits: DebugSnippet[]
  doc_hits: DebugSnippet[]
  identity_info: Record<string, any>
  is_identity_question: boolean
  chat_history: string
}
