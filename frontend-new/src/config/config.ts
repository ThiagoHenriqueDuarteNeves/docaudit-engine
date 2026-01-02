/**
 * Configuração centralizada da aplicação Aurora
 * URLs são lidas de variáveis de ambiente do Vite
 * 
 * Para configurar:
 * - Local: criar arquivo .env.local com VITE_API_URL
 * - Vercel: Settings → Environment Variables
 */

export const API_CONFIG = {
    // URL base da API FastAPI (backend)
    // Configurar no Vercel: Settings → Environment Variables
    baseUrl: import.meta.env.VITE_API_URL || '',

    // Fallback para desenvolvimento local
    localUrl: 'http://localhost:8000',

    // Timeout padrão para requisições (ms)
    timeout: 30000,
} as const;

/**
 * Retorna a URL da API
 * Prioridade: localStorage (usuário) > VITE_API_URL > fallback local
 */
export function getApiUrl(): string {
    // 1. Configuração salva pelo usuário (localStorage) - MAIOR PRIORIDADE
    const stored = localStorage.getItem('lmstudio-settings');
    if (stored) {
        try {
            const settings = JSON.parse(stored);
            if (settings.baseUrl && settings.baseUrl.trim() !== '') {
                return settings.baseUrl;
            }
        } catch {
            // Ignora erro de parse
        }
    }

    // 2. Variável de ambiente (Vercel/Build time)
    if (API_CONFIG.baseUrl) {
        return API_CONFIG.baseUrl;
    }

    // 3. Fallback para localhost (dev)
    return API_CONFIG.localUrl;
}

/**
 * Verifica se está rodando em ambiente de produção
 */
export function isProduction(): boolean {
    return import.meta.env.PROD;
}

/**
 * Verifica se está rodando em ambiente de desenvolvimento
 */
export function isDevelopment(): boolean {
    return import.meta.env.DEV;
}
