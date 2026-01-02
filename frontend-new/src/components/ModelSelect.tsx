/**
 * Componente ModelSelect - Sidebar para selecionar modelos
 */

import { useState, useEffect } from 'react'
import { useSettings } from '../store/settings'
import { listModels, FastAPIError, selectModel } from '../api/fastapi'
import type { Model } from '../types'

interface ModelSelectProps {
  isOpen?: boolean
  onClose?: () => void
}

export function ModelSelect({ isOpen = false, onClose }: ModelSelectProps) {
  const { settings, updateSettings } = useSettings()
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [latency, setLatency] = useState<number | null>(null)
  // Removed [isChecking, setIsChecking]

  // Carrega modelos e verifica latência em uma única requisição
  const loadModels = async () => {
    if (!settings.baseUrl) {
      setError('Configure a Base URL primeiro')
      return
    }

    setLoading(true)
    setError(null)
    const start = performance.now()

    try {
      console.log('🔄 Buscando modelos...', settings.baseUrl)

      // Tenta listar modelos (autodetecta o tipo se necessário na API, ou usa o configurado)
      const response = await listModels(settings.baseUrl, settings.apiKey, settings.backendType)
      const end = performance.now()

      setModels(response.data)
      setLatency(Math.round(end - start)) // Usa o tempo desta requisição como latência

      // Se o backend retornou qual modelo está carregado, usamos ele
      if (response.current) {
        updateSettings({ selectedModel: response.current })
      }
      // Fallback: Se não há modelo selecionado, seleciona o primeiro
      else if (!settings.selectedModel && response.data.length > 0) {
        updateSettings({ selectedModel: response.data[0].id })
      }

      if (response.data.length === 0) {
        setError('⚠️ Nenhum modelo encontrado.')
      }
    } catch (err) {
      console.error('❌ Erro:', err)
      setLatency(null)
      if (err instanceof FastAPIError) {
        setError(`❌ ${err.message}`)
      } else {
        setError(`❌ Erro de conexão`)
      }
    } finally {
      setLoading(false)
    }
  }

  // Carrega modelos apenas quando configurações relevantes mudam
  useEffect(() => {
    loadModels()
  }, [settings.baseUrl, settings.apiKey, settings.backendType])

  // Filtra modelos baseado em search term e prefixo configurado
  const filteredModels = models.filter((model) => {
    const matchesSearch = model.id.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesPrefix = settings.modelPrefixFilter
      ? model.id.startsWith(settings.modelPrefixFilter)
      : true
    return matchesSearch && matchesPrefix
  })

  const handleModelSelect = async (modelId: string) => {
    try {
      // Se for FastAPI, precisamos informar o backend sobre a troca (pois ele mantém estado)
      if (settings.backendType === 'fastapi') {
        setLoading(true)
        await selectModel(settings.baseUrl, modelId)
        console.log('✅ [FastAPI] Modelo atualizado no servidor:', modelId)
      } else {
        console.log('ℹ️ [OpenAI] Seleção local (backend stateless):', modelId)
      }

      updateSettings({ selectedModel: modelId })
      onClose?.()
    } catch (err) {
      console.error('❌ Erro ao selecionar modelo:', err)
      setError(`Erro ao trocar modelo: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      if (settings.backendType === 'fastapi') {
        setLoading(false)
      }
    }
  }

  return (
    <aside className={`model-sidebar ${isOpen ? 'open' : ''} flex flex-col h-full w-full bg-gray-950 border-r border-gray-800 shadow-2xl transition-all duration-300`}>
      <div className="p-4 border-b border-gray-800 bg-gray-900/50 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Aurora
          </h1>

          <div className="flex items-center gap-2">
            {/* Latency Indicator */}
            {latency !== null && (
              <span className="text-xs font-mono text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
                {latency}ms
              </span>
            )}

            {onClose && (
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors p-1"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="Buscar modelo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-gray-950/50 border border-gray-700 rounded-lg py-2 px-3 pl-8 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors"
          />
          <span className="absolute left-2.5 top-2.5 text-gray-500 text-xs">🔍</span>
          <button
            onClick={loadModels}
            className="absolute right-2 top-2 text-gray-400 hover:text-white transition-colors"
            title="Recarregar lista"
          >
            🔄
          </button>
        </div>

        {/* Active Model Display */}
        {settings.selectedModel && (
          <div className="mt-3 px-1">
            <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-2.5">
              <div className="text-[10px] uppercase tracking-wider text-blue-400 font-semibold mb-1">
                Modelo Ativo
              </div>
              <div className="text-xs text-blue-100 font-medium truncate" title={settings.selectedModel}>
                {settings.selectedModel}
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border-b border-red-900/10">
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-40 text-gray-500 space-y-3">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-sm">Carregando modelos...</span>
          </div>
        ) : filteredModels.length === 0 ? (
          <div className="text-center text-gray-500 py-8 text-sm">
            Nenhum modelo encontrado.
          </div>
        ) : (
          filteredModels.map((model) => (
            <button
              key={model.id}
              onClick={() => handleModelSelect(model.id)}
              className={`w-full text-left p-3 rounded-xl transition-all duration-200 group border border-transparent ${settings.selectedModel === model.id
                ? 'bg-blue-600/20 border-blue-500/30 shadow-lg shadow-blue-900/20'
                : 'hover:bg-gray-800/50 hover:border-gray-700'
                }`}
            >
              <div className={`text-sm font-medium truncate mb-0.5 ${settings.selectedModel === model.id ? 'text-blue-200' : 'text-gray-300 group-hover:text-white'
                }`}>
                {model.id}
              </div>
              {/* Hide extensive details to clean up UI, just show relevant info if needed */}
            </button>
          ))
        )}
      </div>

      <div className="p-3 border-t border-gray-800 bg-gray-900/30 text-[10px] text-gray-500 font-mono flex flex-col gap-1">
        <div className="flex justify-between">
          <span>BACKEND:</span>
          <span className={settings.backendType === 'openai' ? 'text-green-500' : 'text-blue-500'}>
            {settings.backendType === 'openai' ? 'OPENAI/LM' : 'FASTAPI'}
          </span>
        </div>
        <div className="truncate opacity-50">{settings.baseUrl}</div>
      </div>
    </aside>
  )
}
