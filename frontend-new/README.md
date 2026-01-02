# LM Studio Front-End

SPA React + TypeScript para conectar com LM Studio via rede local.

## 🚀 Quick Start

1. **Instale as dependências:**
   ```bash
   npm install
   ```

2. **Configure o LM Studio:**
   - Abra o LM Studio
   - Vá em Settings → Server
   - Habilite "CORS" e "Serve on LAN"
   - Anote o IP e porta (ex: `http://192.168.1.10:1234`)

3. **Configure a aplicação:**
   - Copie `.env.example` para `.env`
   - Ajuste `VITE_LMS_BASE_URL` com o IP do LM Studio
   - Ou configure diretamente na UI depois

4. **Execute:**
   ```bash
   npm run dev
   ```

5. **Acesse de outra máquina:**
   - O Vite exibe o IP local (ex: `http://192.168.1.20:5173`)
   - Configure a Base URL no header da aplicação

## 📋 Features

- ✅ Descoberta e listagem de modelos
- ✅ Filtro por prefixo/namespace
- ✅ Chat com streaming SSE
- ✅ Renderização Markdown + syntax highlighting
- ✅ Configuração dinâmica (Base URL, API Key, temperatura, etc.)
- ✅ Persistência local (localStorage)
- ✅ Tratamento de erros CORS/rede
- ✅ Suporte a cancelamento de requisições
- ✅ Responsivo

## 🛠 Estrutura

```
src/
├── api/          # Cliente LM Studio API
├── components/   # Componentes React
├── lib/          # Utilitários (SSE parser)
├── store/        # Context API (configurações)
└── types/        # Tipos TypeScript
```

## 📝 Scripts

- `npm run dev` - Desenvolvimento
- `npm run build` - Build para produção
- `npm run preview` - Preview do build
- `npm run lint` - Lint com ESLint
- `npm run format` - Format com Prettier

## 🔧 Configuração Avançada

### Variáveis de ambiente

- `VITE_LMS_BASE_URL` - URL base do LM Studio (padrão: `http://localhost:1234/v1`)
- `VITE_LMS_API_KEY` - API Key (padrão: `lm-studio`)

### CORS no LM Studio

Se tiver problemas de CORS:
1. LM Studio → Settings → Server
2. Enable "CORS"
3. Reinicie o servidor

## 📦 Deploy

```bash
npm run build
# Upload a pasta dist/ para seu servidor
```

## 🐛 Troubleshooting

**Erro de conexão:**
- Verifique se o LM Studio está rodando
- Confirme que CORS está habilitado
- Teste acessando `http://<IP>:1234/v1/models` no browser

**Modelos não aparecem:**
- Carregue pelo menos um modelo no LM Studio
- Clique em "Recarregar" na sidebar

**Streaming não funciona:**
- Alguns modelos não suportam streaming
- Verifique a console do browser para erros

## 📄 License

MIT
