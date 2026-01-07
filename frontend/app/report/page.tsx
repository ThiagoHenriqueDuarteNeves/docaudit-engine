"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Download, Printer } from "lucide-react";

export default function ReportPage() {
    const router = useRouter();
    const [data, setData] = useState<any>(null);
    const [meta, setMeta] = useState<any>(null);

    useEffect(() => {
        const storedData = localStorage.getItem("lastAnalysisResult");
        const storedMeta = localStorage.getItem("lastAnalysisMeta");

        if (!storedData) {
            // If no data, allow user to go back easily
            return;
        }

        try {
            setData(JSON.parse(storedData));
            if (storedMeta) setMeta(JSON.parse(storedMeta));
        } catch (e) {
            console.error("Failed to parse local storage data", e);
        }
    }, [router]);

    if (!data && !meta) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen space-y-4">
                <p className="text-slate-500">Nenhum relatório encontrado em memória.</p>
                <Button onClick={() => router.push("/")} variant="outline">
                    <ArrowLeft className="mr-2 h-4 w-4" /> Voltar ao Início
                </Button>
            </div>
        );
    }

    const items = data?.items || {};
    const summary = data?.summary || {};

    const handlePrint = () => {
        window.print();
    };

    const handleDownload = () => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `report-${meta?.analysisType || "analysis"}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    return (
        <div className="min-h-screen bg-slate-100 font-sans print:bg-white p-8 print:p-0">
            {/* Action Bar (No print) */}
            <div className="max-w-[210mm] mx-auto mb-6 flex items-center justify-between print:hidden">
                <Button variant="ghost" onClick={() => router.push("/")} className="gap-2">
                    <ArrowLeft className="w-4 h-4" /> Voltar
                </Button>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={handleDownload} className="gap-2">
                        <Download className="w-4 h-4" /> Baixar JSON
                    </Button>
                    <Button onClick={handlePrint} className="gap-2">
                        <Printer className="w-4 h-4" /> Imprimir / PDF
                    </Button>
                </div>
            </div>

            {/* A4 Paper Container */}
            <div className="max-w-[210mm] mx-auto bg-white shadow-lg print:shadow-none print:max-w-none min-h-[297mm] p-[15mm] md:p-[20mm] text-slate-900">

                {/* Header Section */}
                <header className="border-b-2 border-slate-800 pb-6 mb-8">
                    <h1 className="text-3xl font-bold text-slate-900 uppercase tracking-tight mb-4">Relatório de Auditoria</h1>

                    <div className="grid grid-cols-2 gap-y-2 text-sm">
                        <div>
                            <span className="font-semibold text-slate-500 block text-xs uppercase">Documento</span>
                            <span className="font-medium">{(meta?.docIds || []).join(", ")}</span>
                        </div>
                        <div className="text-right">
                            <span className="font-semibold text-slate-500 block text-xs uppercase">Data da Análise</span>
                            <span className="font-medium">{meta?.timestamp ? new Date(meta.timestamp).toLocaleString() : new Date().toLocaleString()}</span>
                        </div>
                        <div className="col-span-2 mt-2">
                            <span className="font-semibold text-slate-500 block text-xs uppercase">Lente de Auditoria</span>
                            <span className="font-medium bg-slate-100 px-2 py-0.5 rounded print:bg-transparent print:p-0">
                                {meta?.analysisType || "N/A"}
                            </span>
                        </div>
                    </div>

                    <p className="text-xs text-slate-400 mt-4 italic print:block">
                        Visualização otimizada para impressão
                    </p>
                </header>

                <div className="space-y-10">

                    {/* 1. Executive Summary */}
                    <section className="break-inside-avoid">
                        <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4 flex items-center gap-2">
                            <span>1. Resumo Executivo</span>
                        </h2>
                        <div className="bg-slate-50 p-6 rounded-lg border border-slate-100 print:border-none print:bg-transparent print:p-0 text-justify leading-relaxed text-slate-800">
                            <p>{summary.executive || "Resumo não disponível."}</p>

                            <div className="mt-4 flex gap-6 text-sm">
                                <div>
                                    <span className="text-slate-500 mr-2">Confiança:</span>
                                    <strong className="text-slate-900">{summary.confidence || "-"}</strong>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* 2. Risks (Risk Detection) */}
                    {(items.risks?.length > 0) && (
                        <section>
                            <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4 flex justify-between items-baseline">
                                <span>2. Riscos Identificados</span>
                                <span className="text-sm font-normal text-slate-500">{items.risks.length} itens</span>
                            </h2>

                            <div className="space-y-4">
                                {items.risks.map((risk: any, idx: number) => (
                                    <div key={idx} className="break-inside-avoid border-l-4 border-red-400 bg-red-50/30 p-4 rounded-r-lg print:bg-transparent print:border-red-300">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="font-bold text-sm text-red-900">
                                                Risco #{idx + 1}
                                            </div>
                                            <div className="flex gap-2">
                                                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${risk.impact === 'alto' ? 'bg-red-200 text-red-800' :
                                                    risk.impact === 'medio' ? 'bg-amber-200 text-amber-800' :
                                                        'bg-slate-200 text-slate-600'
                                                    }`}>
                                                    {risk.impact || 'N/A'}
                                                </span>
                                                <span className="text-[10px] font-medium uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-600 print:border print:border-slate-300">
                                                    {risk.risk_type || 'geral'}
                                                </span>
                                            </div>
                                        </div>
                                        <p className="text-sm text-slate-800 mb-2">{risk.description}</p>
                                        {risk.evidence && (
                                            <p className="text-xs text-slate-500 italic mt-2 pl-2 border-l-2 border-red-200">
                                                Evidência: "{risk.evidence}"
                                            </p>
                                        )}
                                        {risk.justification && (
                                            <p className="text-xs text-slate-600 mt-2">
                                                <span className="font-semibold">Justificativa:</span> {risk.justification}
                                            </p>
                                        )}
                                        {risk.mitigation_question && (
                                            <p className="text-xs text-blue-700 mt-2 bg-blue-50 p-2 rounded print:bg-transparent">
                                                <span className="font-semibold">Pergunta de mitigação:</span> {risk.mitigation_question}
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* 3. Requirements */}
                    {(items.requirements?.length > 0) && (
                        <section>
                            <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4 flex justify-between items-baseline">
                                <span>3. Requisitos Extraídos</span>
                                <span className="text-sm font-normal text-slate-500">{items.requirements.length} itens</span>
                            </h2>

                            <div className="space-y-4">
                                {items.requirements.map((req: any, idx: number) => (
                                    <div key={idx} className="break-inside-avoid border-b border-slate-100 pb-4 last:border-0">
                                        <div className="flex justify-between items-start mb-1">
                                            <div className="font-bold text-sm text-slate-700">
                                                #{req.id || idx + 1} <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 print:border print:border-slate-300">{req.tipo?.toUpperCase() || "REQ"}</span>
                                            </div>
                                            <div className="text-xs font-semibold text-slate-500 uppercase">
                                                {req.testabilidade}
                                            </div>
                                        </div>
                                        <p className="text-sm text-slate-800 mb-1">{req.texto}</p>
                                        {req.evidencia_literal && (
                                            <p className="text-xs text-slate-500 italic mt-1 pl-2 border-l-2 border-slate-200">
                                                "{req.evidencia_literal}"
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* 3. Ambiguities */}
                    {(items.ambiguities?.length > 0) && (
                        <section>
                            <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4">
                                3. Ambiguidades Detectadas <span className="text-sm font-normal text-slate-500 ml-2">({items.ambiguities.length})</span>
                            </h2>
                            <div className="grid grid-cols-1 gap-4">
                                {items.ambiguities.map((amb: any, idx: number) => (
                                    <div key={idx} className="break-inside-avoid bg-amber-50/50 p-4 rounded-lg border border-amber-100 print:bg-transparent print:border-slate-300 print:border">
                                        <div className="mb-2">
                                            <span className="text-xs font-bold text-amber-700 uppercase tracking-wider block mb-1">Problema</span>
                                            <p className="text-sm text-slate-800">{amb.problema}</p>
                                        </div>
                                        <div className="mb-2">
                                            <span className="text-xs font-bold text-green-700 uppercase tracking-wider block mb-1">Sugestão</span>
                                            <p className="text-sm text-slate-800">{amb.sugestao_reescrita}</p>
                                        </div>
                                        {amb.trecho_problematico && (
                                            <div className="mt-2 text-xs text-slate-500 italic bg-white p-2 rounded border border-amber-50 print:border-0 print:p-0 print:bg-transparent">
                                                Trecho: "{amb.trecho_problematico}"
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* 4. Contradictions */}
                    {(items.contradictions?.length > 0) && (
                        <section>
                            <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4">
                                4. Contradições <span className="text-sm font-normal text-slate-500 ml-2">({items.contradictions.length})</span>
                            </h2>
                            <div className="space-y-4">
                                {items.contradictions.map((con: any, idx: number) => (
                                    <div key={idx} className="break-inside-avoid border border-red-100 rounded-lg p-4 bg-red-50/30 print:bg-transparent print:border-slate-300">
                                        <div className="flex justify-between items-center mb-2">
                                            <h4 className="font-bold text-sm text-red-900">Conflito #{idx + 1}</h4>
                                            <span className="text-[10px] font-bold uppercase text-red-600 border border-red-200 px-2 py-0.5 rounded bg-white print:border-slate-400 print:text-slate-800">
                                                {con.severidade}
                                            </span>
                                        </div>
                                        <p className="text-sm text-slate-800 mb-3">{con.descricao}</p>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 print:grid-cols-2">
                                            <div className="text-xs">
                                                <strong className="block text-slate-500 mb-1">Evidência A</strong>
                                                <div className="italic text-slate-700 bg-white p-2 rounded border border-slate-100 print:border-0 print:p-0">"{con.evidencia_a}"</div>
                                            </div>
                                            <div className="text-xs">
                                                <strong className="block text-slate-500 mb-1">Evidência B</strong>
                                                <div className="italic text-slate-700 bg-white p-2 rounded border border-slate-100 print:border-0 print:p-0">"{con.evidencia_b}"</div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* 5. Unverifiable */}
                    {(items.unverifiable_criteria?.length > 0) && (
                        <section>
                            <h2 className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mb-4">
                                5. Requisitos Não Verificáveis <span className="text-sm font-normal text-slate-500 ml-2">({items.unverifiable_criteria.length})</span>
                            </h2>
                            <div className="space-y-3">
                                {items.unverifiable_criteria.map((unv: any, idx: number) => (
                                    <div key={idx} className="break-inside-avoid p-3 border border-purple-100 rounded bg-purple-50/20 print:bg-transparent print:border-slate-300">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-bold text-sm text-purple-900">ID: {unv.id_requisito || "?"}</span>
                                        </div>
                                        <div className="text-sm text-slate-800 mb-1">
                                            <span className="font-semibold text-xs uppercase text-slate-500 mr-2">Motivo:</span>
                                            {unv.motivo}
                                        </div>
                                        <div className="text-sm text-slate-800 mb-2">
                                            <span className="font-semibold text-xs uppercase text-slate-500 mr-2">Sugestão:</span>
                                            {unv.como_tornar_testavel}
                                        </div>
                                        {unv.evidencia_literal && (
                                            <p className="text-xs text-slate-500 italic pl-2 border-l-2 border-purple-200">
                                                "{unv.evidencia_literal}"
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}
                </div>

                {/* Footer */}
                <footer className="mt-16 pt-6 border-t border-slate-200 text-center text-xs text-slate-400 print:mt-8">
                    <p>Gerado por AuditDoc Engine • {new Date().getFullYear()}</p>
                </footer>
            </div>
        </div>
    );
}
