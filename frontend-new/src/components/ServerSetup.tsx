import { useState, useRef, useEffect } from 'react'
import { useSettings } from '../store/settings'
import { checkConnection } from '../api/fastapi'

export function ServerSetup() {
  const { settings, updateSettings } = useSettings()
  // Initialize with existing baseUrl logic (which pulls from env var via settings)
  const [serverUrl, setServerUrl] = useState(settings.baseUrl || '')
  const [isLoading, setIsLoading] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<{
    status: 'idle' | 'testing' | 'success' | 'error'
    message: string
    latency?: number
  }>({
    status: 'idle',
    message: ''
  })

  // Ref for the footer actions to scroll into view
  const footerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll when footer appears (when URL has content)
  useEffect(() => {
    if (serverUrl.length > 0 && footerRef.current) {
      // Small timeout to allow the element to render/animate in
      setTimeout(() => {
        footerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }, 100)
    }
  }, [serverUrl.length > 0]) // Depend on boolean change

  const suggestedServers = [
    {
      name: 'FastAPI Local',
      url: 'http://localhost:8000',
      description: 'Backend FastAPI local (recomendado)',
      icon: '🚀'
    },
    {
      name: 'LM Studio Local',
      url: 'http://localhost:1234',
      description: 'LM Studio rodando localmente',
      icon: '💻'
    },
    {
      name: 'Rede Local',
      url: 'http://192.168.1.7:8000',
      description: 'Servidor na rede local',
      icon: '🏠'
    }
  ]

  // Nota: Para ngrok, digite a URL manualmente no campo abaixo
  // URLs ngrok gratuitas mudam a cada reinicialização

  const formatUrl = (url: string) => {
    if (!url.trim()) return url

    // Remove trailing slash
    // Remove barra final se houver
    let cleanUrl = url.trim().replace(/\/$/, '')

    // Retorna URL limpa (FastAPI não usa /v1)
    return cleanUrl
  }

  const handleTestAndConnect = async () => {
    if (!serverUrl.trim()) {
      setConnectionStatus({
        status: 'error',
        message: '❌ Por favor, insira uma URL válida'
      })
      return
    }

    setIsLoading(true)
    setConnectionStatus({
      status: 'testing',
      message: '🔍 Testando conexão com o servidor...'
    })

    try {
      const formattedUrl = formatUrl(serverUrl.trim())
      const result = await checkConnection(formattedUrl, settings.apiKey)

      if (result !== null) {
        setConnectionStatus({
          status: 'success',
          message: `✅ Conexão estabelecida! (${result.backendType === 'openai' ? 'OpenAI/LM Studio' : 'FastAPI'})`,
          latency: result.latency
        })

        // Salva a configuração e continua
        setTimeout(() => {
          updateSettings({
            baseUrl: formattedUrl,
            serverConfigured: true,
            backendType: result.backendType
          })
        }, 1500)
      } else {
        setConnectionStatus({
          status: 'error',
          message: '❌ Não foi possível conectar ao servidor. Verifique a URL e tente novamente.'
        })
      }
    } catch (error) {
      setConnectionStatus({
        status: 'error',
        message: `❌ Erro: ${error instanceof Error ? error.message : 'Erro desconhecido'}`
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (url: string) => {
    setServerUrl(url)
    setConnectionStatus({ status: 'idle', message: '' })
  }

  const handleSkip = () => {
    // Usa a URL padrão local do LM Studio (localhost) se o usuário pular.
    // Também permite sobrescrever via VITE_API_URL ou VITE_LMS_BASE_URL.
    const defaultLocal = import.meta.env.VITE_API_URL || import.meta.env.VITE_LMS_BASE_URL || 'http://localhost:8000'
    updateSettings({
      baseUrl: defaultLocal,
      serverConfigured: true
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/90 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-2xl bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300 my-auto">

        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600/10 to-purple-600/10 p-8 text-center border-b border-gray-800">
          <div className="w-16 h-16 mx-auto bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg mb-4">
            <img src="/aurora_avatar.png" alt="Aurora" className="w-full h-full object-cover rounded-2xl opacity-90" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">Configuração do Servidor</h1>
          <p className="text-gray-400 text-sm">Configure o servidor de IA para começar</p>
        </div>

        <div className="p-6 space-y-6">
          {/* Suggested Servers */}
          <div className="space-y-4">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">
              Servidores Sugeridos
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {suggestedServers.map((server, index) => (
                <button
                  key={index}
                  onClick={() => handleSuggestionClick(server.url)}
                  disabled={isLoading}
                  className={`flex flex-col items-center gap-3 p-4 rounded-xl border transition-all text-center group relative overflow-hidden h-full ${serverUrl === server.url
                    ? 'bg-blue-600/10 border-blue-500/50 ring-1 ring-blue-500/50'
                    : 'bg-gray-800/50 border-gray-700 hover:bg-gray-800 hover:border-gray-600'
                    }`}
                >
                  <span className="text-3xl group-hover:scale-110 transition-transform duration-300 filter drop-shadow-md">{server.icon}</span>
                  <div className="flex-1 flex flex-col justify-center w-full">
                    <div className={`font-medium text-sm ${serverUrl === server.url ? 'text-blue-400' : 'text-gray-200'}`}>
                      {server.name}
                    </div>
                    {/* Only show URL on hover for grid items to save space, or use smaller font */}
                    <div className="text-[10px] text-gray-500 mt-1 font-mono truncate w-full px-2 opacity-60 group-hover:opacity-100 transition-opacity">
                      {server.url.replace('http://', '')}
                    </div>
                  </div>
                  {serverUrl === server.url && (
                    <div className="absolute top-3 right-3 text-blue-500">
                      <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Custom URL (Zrok focus) */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider block flex justify-between">
              <span>URL Personalizada / Zrok</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={serverUrl}
                onChange={(e) => {
                  setServerUrl(e.target.value)
                  setConnectionStatus({ status: 'idle', message: '' })
                }}
                onKeyPress={(e) => e.key === 'Enter' && handleTestAndConnect()}
                placeholder="Ex: https://seu-tunnel.zrok.io"
                className="w-full bg-gray-950 border border-gray-700 text-white text-base rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent block w-full p-4 pl-4 placeholder-gray-600 font-mono transition-all hover:border-gray-600"
                disabled={isLoading}
              />
            </div>
            {serverUrl.trim() && serverUrl.includes('/v1') && (
              <div className="text-amber-400 text-xs mt-2 flex items-center gap-1 bg-amber-900/10 p-2 rounded">
                ⚠️ Remova o <code className="bg-black/30 px-1 rounded">/v1</code> da URL para FastAPI
              </div>
            )}
          </div>

          {/* Feedback Area */}
          {connectionStatus.status !== 'idle' && (
            <div className={`p-4 rounded-lg flex items-center gap-3 text-sm animate-in fade-in slide-in-from-top-2 ${connectionStatus.status === 'error' ? 'bg-red-900/20 border border-red-900/50 text-red-200' :
              connectionStatus.status === 'success' ? 'bg-green-900/20 border border-green-900/50 text-green-200' :
                'bg-blue-900/10 border border-blue-900/20 text-blue-200'
              }`}>
              {connectionStatus.status === 'testing' && <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />}
              {connectionStatus.status === 'error' && <span>❌</span>}
              {connectionStatus.status === 'success' && <span>✅</span>}
              <div>
                {connectionStatus.message}
                {connectionStatus.latency && <span className="opacity-70 ml-2 text-xs">({connectionStatus.latency}ms)</span>}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions - Only appears on interaction or if URL is pre-filled */}
        {serverUrl.length > 0 && (
          <div
            ref={footerRef}
            className="bg-gray-950 p-6 border-t border-gray-800 flex justify-between items-center gap-4 animate-in slide-in-from-bottom-4 fade-in duration-500"
          >
            <button
              onClick={handleSkip}
              disabled={isLoading}
              className="text-gray-500 hover:text-white text-sm transition-colors px-4 py-2 rounded-lg hover:bg-gray-800"
            >
              Pular configuração
            </button>

            <button
              onClick={handleTestAndConnect}
              disabled={!serverUrl.trim() || isLoading}
              className={`
                  flex-1 px-6 py-3 rounded-lg font-medium text-white shadow-lg shadow-blue-900/20
                  transition-all transform active:scale-95 flex items-center justify-center gap-2
                  ${!serverUrl.trim() || isLoading
                  ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500'}
              `}
            >
              {isLoading ? 'Conectando...' : 'Conectar Servidor'}
              {!isLoading && <span>→</span>}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}