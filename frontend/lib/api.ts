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
