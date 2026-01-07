"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { runAnalyze, uploadDocument, fetchDocuments, DocumentInfo } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FileUp, CheckCircle, Loader2, AlertCircle } from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [docIds, setDocIds] = useState("AuditDocEngine_Demo_SRS_QA_Requisitos.pdf");
  const [analysisType, setAnalysisType] = useState("qa_requirements_audit");
  const [scanAll, setScanAll] = useState(true);
  const [debugLlm, setDebugLlm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload State
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Documents List
  const [availableDocs, setAvailableDocs] = useState<DocumentInfo[]>([]);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    const docs = await fetchDocuments();
    setAvailableDocs(docs);
  };

  const handleUpload = async () => {
    if (!uploadFile) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadDocument(uploadFile);
      setUploadSuccess(`Indexado! ID: ${result.doc_id} (${result.chunks} chunks)`);
      setDocIds(result.doc_id); // Auto-fill
      setUploadFile(null); // Clear input logic if needed, but keeping file selected helps context

      // Refresh list
      await loadDocuments();

    } catch (err: any) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const ids = docIds.split("\n").map(s => s.trim()).filter(Boolean);
      if (ids.length === 0) {
        throw new Error("Informe pelo menos um ID de documento.");
      }

      const result = await runAnalyze({
        document_ids: ids,
        analysis_type: analysisType,
        scan_all: scanAll,
        debug_llm: debugLlm,
      });

      // Save to localStorage for the report page
      localStorage.setItem("lastAnalysisResult", JSON.stringify(result));
      localStorage.setItem("lastAnalysisMeta", JSON.stringify({
        docIds: ids,
        analysisType,
        timestamp: new Date().toISOString()
      }));

      router.push("/report");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans">
      <div className="max-w-2xl mx-auto space-y-8">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">DocAudit Engine</h1>
          <p className="text-slate-500">Frontend MVP para demonstração do pipeline QA Audit.</p>
        </header>

        {/* 1. Upload Section */}
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileUp className="w-5 h-5 text-blue-600" />
              1. Indexar Novo Documento (Opcional)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-4 items-end">
              <div className="flex-1 space-y-2">
                <Label htmlFor="file-upload">Arquivo (PDF, TXT, MD)</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.txt,.md"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
              </div>
              <Button
                onClick={handleUpload}
                disabled={!uploadFile || uploading}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {uploading ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Indexando...</>
                ) : "Indexar"}
              </Button>
            </div>

            {uploadSuccess && (
              <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 p-3 rounded border border-green-200">
                <CheckCircle className="w-4 h-4" />
                {uploadSuccess}
              </div>
            )}
            {uploadError && (
              <div className="flex items-center gap-2 text-sm text-red-700 bg-red-50 p-3 rounded border border-red-200">
                <AlertCircle className="w-4 h-4" />
                {uploadError}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>2. Selecionar Documento</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Presets (Já indexados)</Label>
              <select
                className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-950"
                onChange={(e) => {
                  if (e.target.value) setDocIds(e.target.value);
                }}
              >
                <option value="">-- Selecione documento disponível --</option>
                {availableDocs.map(doc => (
                  <option key={doc.filename} value={doc.filename}>
                    {doc.filename} ({doc.size_mb} MB)
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="docIds">Document IDs (editar livremente)</Label>
              <Textarea
                id="docIds"
                value={docIds}
                onChange={(e) => setDocIds(e.target.value)}
                placeholder="Um ID por linha"
                className="font-mono text-xs"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>3. Configurar Análise</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Lente (Analysis Type)</Label>
              <select
                className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-950"
                value={analysisType}
                onChange={(e) => {
                  setAnalysisType(e.target.value);
                  if (e.target.value === "qa_requirements_audit") setScanAll(true);
                }}
              >
                <option value="qa_requirements_audit">QA Demo Requirements Audit</option>
                <option value="risk_detection">Risk Detection</option>
                <option value="ambiguity_detection">Ambiguity Detection</option>
              </select>
            </div>

            <div className="flex items-center space-x-4 pt-2">
              <label className="flex items-center space-x-2 text-sm">
                <input
                  type="checkbox"
                  checked={scanAll}
                  onChange={(e) => setScanAll(e.target.checked)}
                  className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                />
                <span>Scan All Chunks (Full Retrieval)</span>
              </label>

              <label className="flex items-center space-x-2 text-sm">
                <input
                  type="checkbox"
                  checked={debugLlm}
                  onChange={(e) => setDebugLlm(e.target.checked)}
                  className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                />
                <span>Debug LLM (Logs detalhados)</span>
              </label>
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-900 p-4 rounded-md text-sm">
            <strong>Erro:</strong> {error}
          </div>
        )}

        <Button
          className="w-full h-12 text-lg"
          onClick={handleRun}
          disabled={loading || uploading}
        >
          {loading ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processando Análise...</>
          ) : "Executar Análise"}
        </Button>
      </div>
    </div>
  );
}
