# Ground Truth - DocAudit Engine Evaluation

Este diretório contém os dados anotados manualmente para avaliação da qualidade das análises.

## Estrutura

```
evals/
├── ground_truth/
│   ├── qa_requirements_audit_template.json   # Template para QA Audit
│   ├── risk_detection_template.json          # Template para Riscos
│   └── ambiguity_detection_template.json     # Template para Ambiguidades
└── README.md
```

## Como Usar

### 1. Copie o template para o documento específico

```bash
cp risk_detection_template.json risk_detection_edital_pm.json
```

### 2. Preencha com dados reais

Leia o documento manualmente e anote todos os itens que DEVERIAM ser encontrados:

```json
{
  "document_id": "seu_documento.pdf",
  "expected_items": {
    "risks": [
      {
        "description": "Descrição do risco real...",
        "impact": "alto"
      }
    ]
  }
}
```

### 3. Execute a avaliação

```bash
python evals/evaluate.py --doc "seu_documento.pdf" --type "risk_detection"
```

## Métricas Calculadas

| Métrica | Descrição |
|---------|-----------|
| Precision | Itens corretos / Itens extraídos |
| Recall | Itens encontrados / Itens esperados |
| F1 | Média harmônica de Precision e Recall |

## Dicas para Anotação

1. **Seja exaustivo** - Anote TODOS os itens, mesmo os óbvios
2. **Use evidências literais** - Copie trechos exatos do documento
3. **Classifique corretamente** - Use os tipos definidos (juridico, operacional, etc)
4. **Revise com outro anotador** - Idealmente, 2 pessoas devem anotar independentemente
