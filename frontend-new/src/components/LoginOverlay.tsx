import { useState } from 'react'

interface LoginOverlayProps {
    onLogin: (username: string) => void
}

export function LoginOverlay({ onLogin }: LoginOverlayProps) {
    const [username, setUsername] = useState('')
    const [secret, setSecret] = useState('')
    const [error, setError] = useState('')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()

        const trimmed = username.trim()
        if (!trimmed) {
            setError('Por favor, digite um nome.')
            return
        }

        if (trimmed.length < 3) {
            setError('O nome deve ter pelo menos 3 caracteres.')
            return
        }

        if (trimmed.length > 20) {
            setError('O nome deve ter no máximo 20 caracteres.')
            return
        }

        // onLogin(trimmed) - Modified to include secret
        const combined = `${trimmed}-${secret.trim()}`;
        onLogin(combined)
    }

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                background: '#1e293b',
                padding: '2rem',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                maxWidth: '400px',
                width: '90%',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
            }}>
                <h2 style={{
                    marginTop: 0,
                    marginBottom: '0.5rem',
                    color: '#e2e8f0',
                    fontSize: '1.5rem'
                }}>
                    Bem-vindo(a) ao Chatbot
                </h2>

                <p style={{
                    color: '#94a3b8',
                    marginBottom: '1.5rem',
                    lineHeight: '1.5'
                }}>
                    Por favor, identifique-se para carregar seu histórico de conversas.
                </p>

                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{
                            display: 'block',
                            color: '#cbd5e1',
                            marginBottom: '0.5rem',
                            fontSize: '0.9rem'
                        }}>
                            Seu Nome / Identificação
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Ex: Seu Nome"
                            autoFocus
                            style={{
                                width: '100%',
                                padding: '0.75rem',
                                borderRadius: '8px',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                background: '#0f172a',
                                color: '#fff',
                                fontSize: '1rem'
                            }}
                            maxLength={20}
                        />
                    </div>

                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{
                            display: 'block',
                            color: '#cbd5e1',
                            marginBottom: '0.5rem',
                            fontSize: '0.9rem'
                        }}>
                            Seu Segredo
                        </label>
                        <input
                            type="text"
                            value={secret}
                            onChange={(e) => setSecret(e.target.value)}
                            placeholder="Seu segredo"
                            style={{
                                width: '100%',
                                padding: '0.75rem',
                                borderRadius: '8px',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                background: '#0f172a',
                                color: '#fff',
                                fontSize: '1rem'
                            }}
                            maxLength={20}
                        />
                        <p style={{
                            marginTop: '0.25rem',
                            fontSize: '0.75rem',
                            color: '#94a3b8'
                        }}>
                            * Importante: Isso ainda não é uma senha.
                        </p>
                    </div>

                    {error && (
                        <p style={{
                            color: '#ef4444',
                            fontSize: '0.9rem',
                            marginTop: '-0.5rem',
                            marginBottom: '1rem'
                        }}>
                            {error}
                        </p>
                    )}

                    <button
                        type="submit"
                        style={{
                            width: '100%',
                            padding: '0.75rem',
                            background: '#6366f1',
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            fontSize: '1rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            transition: 'background 0.2s'
                        }}
                    >
                        Entrar
                    </button>
                </form>
            </div>
        </div>
    )
}
