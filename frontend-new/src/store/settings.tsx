/**
 * Context API para gerenciar configurações globais da aplicação
 * Persiste em localStorage
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import type { AppSettings } from '../types'

interface SettingsContextType {
  settings: AppSettings
  updateSettings: (updates: Partial<AppSettings>) => void
  resetSettings: () => void
  resetServerConfig: () => void // Reset apenas config do servidor (para URLs inválidas)
}

const STORAGE_KEY = 'lmstudio-settings'

// Valores padrão das configurações
const defaultSettings: AppSettings = {
  // Não pré-preencher com um túnel público por segurança; deixar em branco como placeholder
  baseUrl: import.meta.env.VITE_API_URL || import.meta.env.VITE_LMS_BASE_URL || '',
  apiKey: import.meta.env.VITE_LMS_API_KEY || 'lm-studio',
  selectedModel: '',
  temperature: 0.7,
  maxTokens: 2048,
  contextWindow: 4096,
  systemPrompt: '',
  modelPrefixFilter: '',
  serverConfigured: false,
  backendType: 'fastapi',
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

/**
 * Provider que gerencia e persiste configurações
 */
export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(() => {
    // Carrega do localStorage na inicialização
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        return { ...defaultSettings, ...JSON.parse(stored) }
      }
    } catch (error) {
      console.warn('Falha ao carregar configurações do localStorage:', error)
    }
    return defaultSettings
  })

  // Persiste no localStorage sempre que settings mudar
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch (error) {
      console.warn('Falha ao salvar configurações no localStorage:', error)
    }
  }, [settings])

  const updateSettings = (updates: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...updates }))
  }

  const resetSettings = () => {
    setSettings(defaultSettings)
    localStorage.removeItem(STORAGE_KEY)
  }

  // Reset apenas configuração do servidor (útil quando URL ngrok muda)
  const resetServerConfig = () => {
    setSettings((prev) => ({
      ...prev,
      baseUrl: '',
      serverConfigured: false,
      selectedModel: ''
    }))
  }

  // Fallback inteligente para URL
  // Prioridade: settings.baseUrl (usuário digitou) > VITE_API_URL (build-time) > '' (tela de config)
  // Se o usuário limpar o campo (string vazia), usa a variável de ambiente
  const effectiveBaseUrl = settings.baseUrl || import.meta.env.VITE_API_URL || ''

  // Valores expostos no contexto
  const contextValue: SettingsContextType = {
    settings: {
      ...settings,
      baseUrl: effectiveBaseUrl // Sobrescreve com o fallback se vazio
    },
    updateSettings,
    resetSettings,
    resetServerConfig
  }

  return (
    <SettingsContext.Provider value={contextValue}>
      {children}
    </SettingsContext.Provider>
  )
}

/**
 * Hook para acessar configurações em componentes
 */
export function useSettings() {
  const context = useContext(SettingsContext)
  if (!context) {
    throw new Error('useSettings deve ser usado dentro de SettingsProvider')
  }
  return context
}
