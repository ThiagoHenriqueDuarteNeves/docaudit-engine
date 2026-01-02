import { useState } from 'react'
import { debugContext } from '../api/fastapi'
import { useSettings } from '../store/settings'
import { DebugResponse, DebugSnippet } from '../types'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

export function ContextDebug() {
    const { settings } = useSettings()
    const { baseUrl } = settings
    const [message, setMessage] = useState('olá')
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<DebugResponse | null>(null)
    const [error, setError] = useState<string | null>(null)

    const handleDebug = async () => {
        if (!message.trim()) return

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const data = await debugContext(baseUrl, message)
            setResult(data)
        } catch (err: any) {
            setError(err.message || 'Erro ao depurar contexto')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex flex-col h-full bg-gray-900 text-gray-100 p-4 pt-24 overflow-y-auto">
            <h2 className="text-xl font-bold mb-4 text-purple-400 text-center md:text-left">🔍 Depurador de Contexto</h2>

            {/* Input Section */}
            <div className="bg-gray-800 p-4 rounded-lg shadow mb-6 border border-gray-700">
                <label className="block text-sm font-medium mb-2 text-gray-300">Mensagem de Teste</label>
                <div className="flex flex-col sm:flex-row gap-2">
                    <input
                        type="text"
                        className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Digite o que o usuário diria..."
                        onKeyDown={(e) => e.key === 'Enter' && handleDebug()}
                    />
                    <button
                        onClick={handleDebug}
                        disabled={loading}
                        className={`px-4 py-2 rounded font-medium transition-colors w-full sm:w-auto ${loading
                            ? 'bg-purple-800 text-gray-400 cursor-not-allowed'
                            : 'bg-purple-600 hover:bg-purple-700 text-white'
                            }`}
                    >
                        {loading ? 'Processando...' : 'Analisar'}
                    </button>
                </div>
                {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
            </div>

            {result && (
                <div className="flex flex-col gap-4">

                    {/* Top Row: Identity + Memory + Documents (side by side on larger screens) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

                        {/* Identity Section */}
                        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                            <h3 className="font-bold text-blue-400 mb-2 text-sm">🆔 Identidade Detectada</h3>
                            <div className="space-y-2 text-sm">
                                <div className="bg-gray-700 p-2 rounded">
                                    <span className="text-gray-400 block text-xs">Pergunta de Identidade?</span>
                                    <span className={result.is_identity_question ? "text-green-400 font-bold" : "text-gray-300"}>
                                        {result.is_identity_question ? "SIM" : "NÃO"}
                                    </span>
                                </div>
                                {Object.entries(result.identity_info).map(([key, val]) => (
                                    val && (
                                        <div key={key} className="bg-gray-700 p-2 rounded">
                                            <span className="text-gray-400 block text-xs capitalize">{key.replace('_', ' ')}</span>
                                            <span className="text-white text-xs">{String(val)}</span>
                                        </div>
                                    )
                                ))}
                            </div>
                        </div>

                        {/* Memory Hits */}
                        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden flex flex-col max-h-[250px]">
                            <div className="bg-gray-900 px-3 py-2 border-b border-gray-700 font-bold text-green-400 flex justify-between text-sm">
                                <span>🧠 Memórias Recuperadas</span>
                                <span className="bg-gray-700 text-xs px-2 py-0.5 rounded text-white">{result.mem_hits.length}</span>
                            </div>
                            <div className="p-3 overflow-y-auto space-y-2 flex-1">
                                {result.mem_hits.length === 0 ? (
                                    <p className="text-gray-500 text-xs italic">Nenhuma memória relevante encontrada.</p>
                                ) : (
                                    result.mem_hits.map((hit, idx) => (
                                        <SnippetCard key={idx} hit={hit} color="border-green-800" />
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Document Hits */}
                        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden flex flex-col max-h-[250px]">
                            <div className="bg-gray-900 px-3 py-2 border-b border-gray-700 font-bold text-orange-400 flex justify-between text-sm">
                                <span>📚 Documentos Recuperados</span>
                                <span className="bg-gray-700 text-xs px-2 py-0.5 rounded text-white">{result.doc_hits.length}</span>
                            </div>
                            <div className="p-3 overflow-y-auto space-y-2 flex-1">
                                {result.doc_hits.length === 0 ? (
                                    <p className="text-gray-500 text-xs italic">Nenhum documento relevante encontrado.</p>
                                ) : (
                                    result.doc_hits.map((hit, idx) => (
                                        <SnippetCard key={idx} hit={hit} color="border-orange-800" />
                                    ))
                                )}
                            </div>
                        </div>

                    </div>

                    {/* Chat History (from SQLite) */}
                    <div className="bg-gray-800 rounded-lg border border-cyan-700 overflow-hidden">
                        <div className="bg-gray-900 px-4 py-2 border-b border-cyan-700 font-bold text-cyan-400 flex justify-between text-sm">
                            <span>💬 Histórico de Chat (SQL)</span>
                            <span className="text-xs text-gray-400 font-normal">Últimas mensagens do banco de dados</span>
                        </div>
                        <div className="p-3 overflow-y-auto max-h-[200px]">
                            {result.chat_history ? (
                                <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">{result.chat_history}</pre>
                            ) : (
                                <p className="text-gray-500 text-xs italic">Nenhum histórico recente.</p>
                            )}
                        </div>
                    </div>

                    {/* Bottom: Full width Prompt */}
                    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                        <div className="bg-gray-900 px-4 py-2 border-b border-gray-700 font-bold text-yellow-500">
                            📝 Prompt Final ( Raw )
                        </div>
                        <div className="p-0 overflow-x-auto">
                            <SyntaxHighlighter
                                language="markdown"
                                style={vscDarkPlus}
                                customStyle={{ margin: 0, fontSize: '0.8rem', maxHeight: '400px' }}
                                wrapLines={true}
                                wrapLongLines={true}
                            >
                                {result.formatted_prompt}
                            </SyntaxHighlighter>
                        </div>
                    </div>

                </div>
            )}
        </div>
    )
}

function SnippetCard({ hit, color }: { hit: DebugSnippet, color: string }) {
    const isUser = hit.source === 'user'
    return (
        <div className={`bg-gray-900/50 rounded border ${color} p-3 text-sm`}>
            <div className="flex justify-between items-start mb-1">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${isUser ? 'bg-blue-900 text-blue-300' : 'bg-gray-700 text-gray-300'}`}>
                    {hit.source}
                </span>
                {hit.score !== undefined && hit.score !== null && (
                    <span className="text-xs text-gray-500">score: {hit.score.toFixed(3)}</span>
                )}
            </div>
            <p className="text-gray-300 whitespace-pre-wrap font-mono text-xs">{hit.text}</p>
            {hit.metadata?.timestamp && (
                <div className="mt-2 text-xs text-gray-600 border-t border-gray-700 pt-1">
                    {new Date(hit.metadata.timestamp).toLocaleString()}
                </div>
            )}
        </div>
    )
}
