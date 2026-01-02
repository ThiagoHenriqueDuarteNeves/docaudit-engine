
export class FastAPIError extends Error {
    constructor(public message: string, public status?: number, public originalError?: any) {
        super(message);
        this.name = 'FastAPIError';
    }
}

export interface ChatCompletionChunk {
    id: string;
    object: string;
    created: number;
    model: string;
    choices: {
        index: number;
        delta: {
            role?: string;
            content?: string;
        };
        finish_reason: string | null;
    }[];
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper to add tunnel bypass headers
const getHeaders = (existing: HeadersInit = {}): HeadersInit => {
    const headers = new Headers(existing);
    headers.append('ngrok-skip-browser-warning', 'true');
    headers.append('Bypass-Tunnel-Reminder', 'true');
    headers.append('skip_zrok_interstitial', 'true');
    return headers;
};

export async function checkConnection(baseUrl: string = DEFAULT_BASE_URL, _apiKey?: string): Promise<{ backendType: 'fastapi' | 'openai', latency: number } | null> {
    const start = performance.now();
    try {
        const response = await fetch(`${baseUrl}/api/health`, {
            method: 'GET',
            headers: getHeaders()
        });
        const end = performance.now();

        if (response.ok) {
            return {
                backendType: 'fastapi',
                latency: Math.round(end - start)
            };
        }
        return null;
    } catch (error) {
        console.error('Connection check failed:', error);
        return null;
    }
}

export async function listModels(baseUrl: string = DEFAULT_BASE_URL, _apiKey?: string, _backendType?: string): Promise<{ data: { id: string; object: 'model' }[], current?: string }> {
    const response = await fetch(`${baseUrl}/api/models`, {
        headers: getHeaders()
    });
    if (!response.ok) throw new FastAPIError('Failed to list models', response.status);

    const data = await response.json();
    const models = (data.models || []).map((m: string) => ({
        id: m,
        object: 'model' as const
    }));

    return {
        data: models,
        current: models.length > 0 ? models[0].id : undefined
    };
}

export async function selectModel(baseUrl: string = DEFAULT_BASE_URL, model: string): Promise<string> {
    const response = await fetch(`${baseUrl}/api/model/select`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ model }),
    });
    if (!response.ok) {
        const err = await response.text();
        throw new FastAPIError(`Failed to select model: ${err}`, response.status);
    }
    const data = await response.json();
    return data.message;
}

export async function listDocuments(baseUrl: string = DEFAULT_BASE_URL): Promise<any[]> {
    const response = await fetch(`${baseUrl}/api/documents`, {
        headers: getHeaders()
    });
    if (!response.ok) throw new FastAPIError('Failed to list documents', response.status);
    return await response.json();
}

export async function uploadDocument(baseUrl: string = DEFAULT_BASE_URL, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    // Note: Do NOT set Content-Type for FormData, fetch handles it
    const response = await fetch(`${baseUrl}/api/documents/upload`, {
        method: 'POST',
        headers: getHeaders(),
        body: formData,
    });
    if (!response.ok) {
        const err = await response.text();
        throw new FastAPIError(`Upload failed: ${err}`, response.status);
    }
    return await response.json();
}

export async function deleteDocument(baseUrl: string = DEFAULT_BASE_URL, filename: string): Promise<any> {
    const response = await fetch(`${baseUrl}/api/documents/${filename}`, {
        method: 'DELETE',
        headers: getHeaders()
    });
    if (!response.ok) {
        const err = await response.text();
        throw new FastAPIError(`Delete failed: ${err}`, response.status);
    }
    return await response.json();
}

export async function reindexDocuments(baseUrl: string = DEFAULT_BASE_URL): Promise<any> {
    const response = await fetch(`${baseUrl}/api/documents/reindex`, {
        method: 'POST',
        headers: getHeaders()
    });
    if (!response.ok) {
        const err = await response.text();
        throw new FastAPIError(`Reindex failed: ${err}`, response.status);
    }
    return await response.json();
}

export async function debugContext(baseUrl: string = DEFAULT_BASE_URL, message: string): Promise<any> {
    const response = await fetch(`${baseUrl}/api/debug/context`, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message, history: [] })
    });
    if (!response.ok) throw new FastAPIError('Debug context failed', response.status);
    return await response.json();
}


export async function* chatStream(
    baseUrl: string,
    _apiKey: string,
    request: any,
    abortController?: AbortController,
    _backendType: 'fastapi' | 'openai' | 'anthropic' = 'fastapi'
): AsyncGenerator<ChatCompletionChunk, void, unknown> {

    const userMessage = request.messages[request.messages.length - 1]?.content || '';
    const requestImage = (request as any).image;

    // Setup headers with bypass
    const headers = getHeaders();

    const formData = new FormData();
    formData.append("message", userMessage);
    formData.append("history", JSON.stringify(request.messages.slice(0, -1)));

    if (requestImage && requestImage instanceof File) {
        formData.append("image", requestImage);
    }

    try {
        const response = await fetch(`${baseUrl}/api/chat`, {
            method: 'POST',
            headers,
            body: formData,
            signal: abortController?.signal,
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new FastAPIError(`Chat failed: ${response.statusText} - ${errorText}`, response.status);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) throw new FastAPIError('Response body is null');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            if (chunk) {
                yield {
                    id: 'fastapi-' + Date.now(),
                    object: 'chat.completion.chunk',
                    created: Date.now(),
                    model: request.model,
                    choices: [
                        {
                            index: 0,
                            delta: {
                                role: 'assistant',
                                content: chunk,
                            },
                            finish_reason: null,
                        },
                    ],
                };
            }
        }
    } catch (error: any) {
        if (error.name === 'AbortError') return;
        throw new FastAPIError(error.message || 'Network error', undefined, error);
    }
}
