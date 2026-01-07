const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8002";

interface AnalyzeParams {
    document_ids: string[];
    analysis_type: string;
    scan_all: boolean;
    debug_llm: boolean;
    question?: string;
    max_items_per_category?: number;
}

export async function runAnalyze(params: AnalyzeParams) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(params),
        });

        const data = await response.json();

        if (!response.ok) {
            // If response is not ok, but returns JSON with error/detail
            const msg = data.message || data.error || data.detail || `Erro HTTP ${response.status}`;
            throw new Error(msg);
        }

        // Check if data itself has "error" field (some backends return 200 but {error: ...})
        if (data.error) {
            throw new Error(data.message || data.error);
        }

        return data;
    } catch (error: any) {
        console.error("Analyze error:", error);
        throw new Error(error.message || "Falha na comunicação com o servidor.");
    }
}

export async function uploadDocument(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    // Optional: formData.append("doc_id", ...); 

    try {
        const response = await fetch(`${API_BASE_URL}/api/index`, {
            method: "POST",
            body: formData, // fetch sets content-type multipart automatically
        });

        const data = await response.json();

        if (!response.ok) {
            const msg = data.message || data.error || data.detail || `Erro HTTP ${response.status}`;
            throw new Error(msg);
        }

        return data; // { doc_id, status, chunks, filename, message }
    } catch (error: any) {
        console.error("Upload error:", error);
        throw new Error(error.message || "Falha no upload do documento.");
    }
}

export interface DocumentInfo {
    filename: string;
    size_bytes: number;
    size_mb: number;
    modified: string;
    hash: string;
}

export async function fetchDocuments(): Promise<DocumentInfo[]> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/documents`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Erro ao listar documentos");
        }

        return data.documents || [];
    } catch (error: any) {
        console.error("Fetch docs error:", error);
        return [];
    }
}

// ============================================================================
// ANALYZE WITH PROGRESS POLLING
// ============================================================================

export interface AnalyzeJobStatus {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    batch_current?: number;
    batch_total?: number;
    percent?: number;
    message?: string;
    result?: any;
    error?: string;
}

export interface ProgressInfo {
    batch: number;
    total: number;
    percent: number;
    message: string;
}

/**
 * Start an analyze job (returns immediately with job_id)
 */
export async function startAnalyze(params: AnalyzeParams): Promise<AnalyzeJobStatus> {
    const response = await fetch(`${API_BASE_URL}/api/analyze/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || data.error || "Erro ao iniciar análise");
    }

    return data;
}

/**
 * Poll job status
 */
export async function pollAnalyzeStatus(jobId: string): Promise<AnalyzeJobStatus> {
    const response = await fetch(`${API_BASE_URL}/api/analyze/status/${jobId}`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || data.error || "Erro ao verificar status");
    }

    return data;
}

/**
 * Run analyze with progress callback (uses polling internally)
 */
export async function runAnalyzeWithProgress(
    params: AnalyzeParams,
    onProgress: (info: ProgressInfo) => void,
    pollIntervalMs: number = 2000
): Promise<any> {
    // 1. Start the job
    const job = await startAnalyze(params);
    const jobId = job.job_id;

    console.log(`[API] Job started: ${jobId}`);

    // 2. Poll until done
    return new Promise((resolve, reject) => {
        const poll = async () => {
            try {
                const status = await pollAnalyzeStatus(jobId);

                // Report progress
                onProgress({
                    batch: status.batch_current || 0,
                    total: status.batch_total || 0,
                    percent: status.percent || 0,
                    message: status.message || ""
                });

                if (status.status === 'completed') {
                    console.log(`[API] Job ${jobId} completed`);
                    resolve(status.result);
                } else if (status.status === 'failed') {
                    console.error(`[API] Job ${jobId} failed:`, status.error);
                    reject(new Error(status.error || "Análise falhou"));
                } else {
                    // Still running, poll again
                    setTimeout(poll, pollIntervalMs);
                }
            } catch (err) {
                reject(err);
            }
        };

        // Start polling after a short delay
        setTimeout(poll, 500);
    });
}
