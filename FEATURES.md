# Features First Workflow

Este projeto segue um fluxo "features first": cada feature tem uma branch dedicada, um checklist leve e commits pequenos.

## Estrutura

- `FEATURES.md`: este guia.
- `feature-template.md`: template de feature.

## Passo a passo (feature)

1) Criar branch
```
git checkout -b feature/<nome-curto>
```

2) Criar o arquivo da feature
```
cp feature-template.md <nome-curto>.md
```

3) Preencher checklist
- objetivo
- escopo
- criterios de aceite
- riscos conhecidos
- testes esperados

4) Implementar com commits pequenos
- 1 commit = 1 ideia
- mensagens claras (ex.: `feat: add reranker multilingual`)

5) Encerrar feature
- checklist completo
- testes rodados (ou justificar)
- merge para `main`/`develop`

## Conven??es

- Branch: `feature/<nome-curto>`
- Commit: `feat:` `fix:` `chore:` `docs:` `refactor:` `test:`
- Evitar commits grandes e mistos

## Exemplo r?pido

```
git checkout -b feature/reranker-multilingual
cp feature-template.md reranker-multilingual.md
# editar e marcar checklist
```
