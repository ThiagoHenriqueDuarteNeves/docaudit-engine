"use client";

import { useEffect, useState } from "react";
import { fetchModels, selectModel } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Settings2, Check, X } from "lucide-react";

export function ModelSelector() {
    const [isOpen, setIsOpen] = useState(false);
    const [models, setModels] = useState<string[]>([]);
    const [currentModel, setCurrentModel] = useState<string>("");
    const [loading, setLoading] = useState(false);
    const [changing, setChanging] = useState(false);

    // Load initial state
    useEffect(() => {
        loadModels();
    }, []);

    const loadModels = async () => {
        try {
            setLoading(true);
            const data = await fetchModels();
            setModels(data.models);
            // Expected "Modelo atual: nome" or just "nome" fallback
            const cleanName = data.current.replace("Modelo atual: ", "").replace("Modelo: ", "");
            setCurrentModel(cleanName);
        } catch (e) {
            console.error("Failed to load models", e);
        } finally {
            setLoading(false);
        }
    };

    const handleSelect = async (model: string) => {
        try {
            setChanging(true);
            await selectModel(model);
            setCurrentModel(model);
            setIsOpen(false);
        } catch (e) {
            alert("Erro ao trocar modelo: " + e);
        } finally {
            setChanging(false);
        }
    };

    if (loading && !currentModel) return <div className="text-xs text-slate-400">Carregando modelos...</div>;

    return (
        <>
            <Button
                variant="outline"
                onClick={() => { setIsOpen(true); loadModels(); }}
                className="flex items-center gap-2 text-xs h-8 px-3 bg-white/50 border-slate-200 hover:bg-white"
            >
                <Settings2 className="w-3 h-3" />
                <span className="opacity-70">Modelo:</span>
                <span className="font-semibold truncate max-w-[150px]">{currentModel || "Unknown"}</span>
            </Button>

            {/* Simple Modal Overlay */}
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
                    <div className="bg-white rounded-lg shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                                <Settings2 className="w-4 h-4 text-blue-600" />
                                Selecionar Modelo LLM
                            </h3>
                            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-2 max-h-[60vh] overflow-y-auto">
                            {models.length === 0 ? (
                                <div className="p-8 text-center text-slate-500">Nenhum modelo encontrado.</div>
                            ) : (
                                <div className="space-y-1">
                                    {models.map((model) => {
                                        const isSelected = currentModel === model;
                                        return (
                                            <button
                                                key={model}
                                                onClick={() => handleSelect(model)}
                                                disabled={changing}
                                                className={`w-full text-left px-4 py-3 rounded-md text-sm transition-colors flex items-center justify-between
                                                    ${isSelected
                                                        ? "bg-blue-50 text-blue-700 font-medium ring-1 ring-blue-200"
                                                        : "hover:bg-slate-50 text-slate-700"
                                                    }
                                                `}
                                            >
                                                <span className="truncate">{model}</span>
                                                {isSelected && <Check className="w-4 h-4" />}
                                                {changing && isSelected && <Loader2 className="w-4 h-4 animate-spin" />}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        <div className="px-6 py-3 bg-slate-50 text-xs text-center text-slate-400 border-t border-slate-100">
                            LM Studio Bridge
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
