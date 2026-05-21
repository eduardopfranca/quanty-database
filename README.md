# Quanty Database

Plataforma web para atualização e gestão de bases de dados financeiras a partir de múltiplos provedores de dados.

Atualmente suporta:

- **Varos** (B3, indicadores fundamentalistas, cotações)

## Arquitetura

- **Frontend** (`apps/web`) — Next.js 14, hospedado no Vercel
- **Worker** (`apps/worker`) — FastAPI em Python, hospedado no Render
- **Banco de metadados e configs** — Supabase Postgres
- **Storage de arquivos parquet** — Supabase Storage

## Fluxo

1. Usuário seleciona os fatores desejados na interface web
2. Frontend dispara um job no worker
3. Worker baixa os componentes brutos da Varos, calcula indicadores derivados (graham, EBIT_EV, ROIC, etc.)
4. Worker salva os parquets no Supabase Storage e grava o relatório de completude no Postgres
5. Frontend exibe o relatório de completude pro usuário

## Estrutura do repositório

\`\`\`
quanty-database/
├── apps/
│   ├── web/          # Next.js (Vercel)
│   └── worker/       # FastAPI (Render)
│       └── src/
│           ├── providers/    # Abstração de provedores de dados
│           ├── indicators/   # Cálculo de indicadores derivados
│           ├── jobs/         # Pipeline de atualização
│           └── storage/      # Integração com Supabase Storage
├── .env.example
├── .gitignore
└── README.md
\`\`\`

## Setup local

(documentação detalhada será adicionada conforme avançamos)

## Status

🚧 Em desenvolvimento — v1
