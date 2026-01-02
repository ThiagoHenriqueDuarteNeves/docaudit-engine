/**
 * Componente DocumentsTab - Gerenciamento de documentos RAG
 */

import { useState, useEffect } from 'react'
import { useSettings } from '../store/settings'
import { uploadDocument, listDocuments, deleteDocument, reindexDocuments, FastAPIError } from '../api/fastapi'

interface Document {
  filename: string
  size: string
  date: string
}

export function DocumentsTab() {
  const { settings } = useSettings()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadDocuments = async () => {
    if (!settings.baseUrl) {
      setError('Configure a Base URL primeiro')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const docs = await listDocuments(settings.baseUrl)
      setDocuments(docs)
    } catch (err) {
      console.error('❌ Erro ao listar documentos:', err)
      if (err instanceof FastAPIError) {
        setError(err.message)
      } else {
        setError('Erro ao listar documentos')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Valida tipo de arquivo
    const validExtensions = ['.pdf', '.txt', '.md']
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))

    if (!validExtensions.includes(fileExtension)) {
      setError(`Tipo de arquivo inválido. Use: ${validExtensions.join(', ')}`)
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const result = await uploadDocument(settings.baseUrl, file)
      setSuccess(result.message || 'Documento enviado com sucesso!')
      await loadDocuments() // Recarrega lista

      // Limpa input
      event.target.value = ''
    } catch (err) {
      console.error('❌ Erro ao fazer upload:', err)
      if (err instanceof FastAPIError) {
        setError(err.message)
      } else {
        setError('Erro ao fazer upload do documento')
      }
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`Deseja realmente deletar "${filename}"?`)) {
      return
    }

    setError(null)
    setSuccess(null)

    try {
      const result = await deleteDocument(settings.baseUrl, filename)
      setSuccess(result.message || 'Documento removido com sucesso!')
      await loadDocuments() // Recarrega lista
    } catch (err) {
      console.error('❌ Erro ao deletar documento:', err)
      if (err instanceof FastAPIError) {
        setError(err.message)
      } else {
        setError('Erro ao deletar documento')
      }
    }
  }

  const handleReindex = async () => {
    setError(null)
    setSuccess(null)
    setLoading(true)

    try {
      const result = await reindexDocuments(settings.baseUrl)
      setSuccess(result.message || 'Reindexação iniciada com sucesso!')

      // Pequeno delay para dar tempo de começar
      setTimeout(() => loadDocuments(), 2000)
    } catch (err) {
      console.error('❌ Erro ao reindexar:', err)
      if (err instanceof FastAPIError) {
        setError(err.message)
      } else {
        setError('Erro ao reindexar documentos')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [settings.baseUrl])

  return (
    <div className="documents-tab" style={{ paddingTop: '6rem', display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
      <div className="documents-header" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
        <h2>📚 Documentos RAG</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={handleReindex}
            disabled={loading}
            className="btn-primary"
            style={{
              padding: '0.5rem 1rem',
              background: 'rgba(34, 197, 94, 0.2)',
              border: '1px solid rgba(34, 197, 94, 0.5)',
              borderRadius: '8px',
              cursor: loading ? 'not-allowed' : 'pointer',
              color: 'rgb(34, 197, 94)',
              fontSize: '0.9rem'
            }}
            title="Reindexar todos os documentos"
          >
            {loading ? '⏳ Indexando...' : '🔄 Reindexar'}
          </button>
          <button
            onClick={loadDocuments}
            disabled={loading}
            className="btn-icon"
            title="Recarregar lista"
          >
            {loading ? '⏳' : '🔄'}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-message" style={{ margin: '1rem 0' }}>
          ❌ {error}
        </div>
      )}

      {success && (
        <div className="success-message">
          ✅ {success}
        </div>
      )}

      <div className="upload-section" style={{ width: '100%', maxWidth: '600px' }}>
        <label htmlFor="file-upload" className="upload-label">
          <input
            id="file-upload"
            type="file"
            accept=".pdf,.txt,.md"
            onChange={handleUpload}
            disabled={uploading}
            style={{ display: 'none' }}
          />
          {uploading ? (
            <div>⏳ Enviando...</div>
          ) : (
            <div>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📤</div>
              <div>Clique para fazer upload</div>
              <div style={{ fontSize: '0.8rem', opacity: 0.7, marginTop: '0.5rem' }}>
                PDF, TXT ou MD (máx. 10MB)
              </div>
            </div>
          )}
        </label>
      </div>

      <div className="documents-list" style={{ width: '100%', maxWidth: '600px' }}>
        {loading ? (
          <div className="loading-state">Carregando documentos...</div>
        ) : documents.length === 0 ? (
          <div className="empty-state" style={{
            padding: '2rem',
            textAlign: 'center',
            opacity: 0.7
          }}>
            Nenhum documento indexado
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {documents.map((doc) => (
              <div key={doc.filename} className="document-item">
                <div className="document-info">
                  <span className="document-icon">📄</span>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="document-name" title={doc.filename}>
                      {doc.filename}
                    </span>
                    <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>
                      {doc.size} • {doc.date}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.filename)}
                  className="btn-icon"
                  style={{
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: 'rgb(239, 68, 68)',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.8rem',
                    flexShrink: 0
                  }}
                  title={`Deletar ${doc.filename}`}
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="documents-footer" style={{
        marginTop: '1rem',
        padding: '0.75rem',
        background: 'rgba(0, 0, 0, 0.1)',
        borderRadius: '8px',
        fontSize: '0.8rem',
        opacity: 0.8
      }}>
        📊 Total: {documents.length} documento{documents.length !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
