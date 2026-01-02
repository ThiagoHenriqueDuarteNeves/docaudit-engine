/**
 * Componente Header - Barra superior com configurações
 */

import { useState } from 'react'
import { useSettings } from '../store/settings'

interface HeaderProps {
  onMenuClick?: () => void
  onLogout?: () => void
  username?: string | null
  isFullScreen?: boolean
  onToggleFullScreen?: () => void
  activeTab?: 'chat' | 'documents' | 'debug'
  onTabChange?: (tab: 'chat' | 'documents' | 'debug') => void
}

export function Header({
  onMenuClick,
  onLogout,
  username,
  isFullScreen,
  onToggleFullScreen,
  activeTab,
  onTabChange
}: HeaderProps) {
  const { settings, updateSettings, resetServerConfig } = useSettings()
  const [isExpanded, setIsExpanded] = useState(false)



  const handleSave = () => {
    setIsExpanded(false)
    // As configurações já são salvas automaticamente pelo Context
  }

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          {onMenuClick && (
            <button
              className="btn-menu-toggle"
              onClick={onMenuClick}
              title="Menu de Modelos"
              aria-label="Abrir menu de modelos"
            >
              ☰
            </button>
          )}

          {username && (
            <span className="username-display btn-settings" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: '0.5rem' }}>
              👤 <span className="btn-label">{username}</span>
            </span>
          )}

        </div>

        <div className="header-center">
          {/* Central area empty for now */}
        </div>

        <div className="header-actions">
          {/* Navigation Tabs */}
          <button
            className={`btn-settings ${activeTab === 'chat' ? 'active-tab' : ''}`}
            onClick={() => onTabChange && onTabChange('chat')}
            style={activeTab === 'chat' ? { background: 'rgba(99, 102, 241, 0.2)', borderColor: 'rgba(99, 102, 241, 0.5)' } : {}}
          >
            💬 <span className="btn-label">Chat</span>
          </button>
          <button
            className={`btn-settings ${activeTab === 'documents' ? 'active-tab' : ''}`}
            onClick={() => onTabChange && onTabChange('documents')}
            style={activeTab === 'documents' ? { background: 'rgba(99, 102, 241, 0.2)', borderColor: 'rgba(99, 102, 241, 0.5)' } : {}}
          >
            📚 <span className="btn-label">Docs</span>
          </button>
          <button
            className={`btn-settings ${activeTab === 'debug' ? 'active-tab' : ''}`}
            onClick={() => onTabChange && onTabChange('debug')}
            style={activeTab === 'debug' ? { background: 'rgba(168, 85, 247, 0.2)', borderColor: 'rgba(168, 85, 247, 0.5)' } : {}}
          >
            🔍 <span className="btn-label">Debug</span>
          </button>

          <div className="divider" style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.1)', margin: '0 0.5rem' }}></div>

          {onToggleFullScreen && (
            <button
              className="btn-settings"
              onClick={onToggleFullScreen}
              title={isFullScreen ? "Sair da Tela Cheia" : "Expandir Chat"}
            >
              {isFullScreen ? "❌" : "📺"} <span className="btn-label">{isFullScreen ? "" : "Expandir"}</span>
            </button>
          )}
          <button
            className="btn-settings"
            onClick={() => setIsExpanded(!isExpanded)}
            title="Configurações"
          >
            ⚙️ <span className="btn-label">Config</span>
          </button>
          <button
            className="btn-reset"
            onClick={() => {
              resetServerConfig()
            }}
            title="Alterar servidor"
            style={{
              background: '#f59e0b',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              padding: '0.5rem',
              cursor: 'pointer',
              fontSize: '0.8rem'
            }}
          >
            🔄 <span className="btn-label">Servidor</span>
          </button>
          {onLogout && (
            <button
              onClick={onLogout}
              className="btn-settings"
              style={{
                borderColor: 'rgba(239, 68, 68, 0.3)',
                color: '#ef4444',
              }}
              title="Sair"
            >
              🚪 <span className="btn-label">Sair</span>
            </button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="settings-panel">
          <div className="settings-grid">
            <div className="setting-item">
              <label>
                🌐 Base URL do Servidor
                <input
                  type="text"
                  value={settings.baseUrl}
                  onChange={(e) => updateSettings({ baseUrl: e.target.value })}
                  placeholder="https://b24acee44135.ngrok-free.app"
                  className="server-url-input"
                />
              </label>
              <small>URL do servidor FastAPI (sem /v1). Ex: https://b24acee44135.ngrok-free.app</small>
              <small style={{ display: 'block', marginTop: '4px', color: '#64748b' }}>
                💡 Dica: Deixe em branco para usar a URL padrão do ambiente: <code>{import.meta.env.VITE_API_URL || 'Localhost'}</code>
              </small>
            </div>

            <div className="setting-item">
              <label>
                API Key
                <input
                  type="text"
                  value={settings.apiKey}
                  onChange={(e) => updateSettings({ apiKey: e.target.value })}
                  placeholder="lm-studio"
                />
              </label>
              <small>Chave de API (padrão: lm-studio)</small>
            </div>

            <div className="setting-item">
              <label>
                Temperature
                <input
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
                />
              </label>
              <small>Criatividade (0-2)</small>
            </div>

            <div className="setting-item">
              <label>
                Max Tokens
                <input
                  type="number"
                  min="1"
                  max="32000"
                  step="128"
                  value={settings.maxTokens}
                  onChange={(e) => updateSettings({ maxTokens: parseInt(e.target.value) })}
                />
              </label>
              <small>Limite de tokens na resposta</small>
            </div>

            <div className="setting-item">
              <label>
                Context Window
                <input
                  type="number"
                  min="512"
                  max="200000"
                  step="512"
                  value={settings.contextWindow}
                  onChange={(e) => updateSettings({ contextWindow: parseInt(e.target.value) })}
                />
              </label>
              <small>Tamanho da janela de contexto (tokens)</small>
            </div>

            <div className="setting-item full-width">
              <label>
                System Prompt
                <textarea
                  value={settings.systemPrompt}
                  onChange={(e) => updateSettings({ systemPrompt: e.target.value })}
                  placeholder="Você é um assistente útil..."
                  rows={3}
                />
              </label>
              <small>Instrução inicial para o modelo</small>
            </div>

            <div className="setting-item">
              <label>
                Filtro de Prefixo
                <input
                  type="text"
                  value={settings.modelPrefixFilter}
                  onChange={(e) => updateSettings({ modelPrefixFilter: e.target.value })}
                  placeholder="gpt-oss/, qwen/, openai/"
                />
              </label>
              <small>Filtrar modelos por prefixo (ex: gpt-oss/)</small>
            </div>
          </div>

          <div className="settings-actions">
            <button className="btn-primary" onClick={handleSave}>
              ✅ Salvar e Fechar
            </button>
          </div>
        </div>
      )}
    </header>
  )
}
