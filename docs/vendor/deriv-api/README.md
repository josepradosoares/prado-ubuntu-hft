# Documentação Oficial Offline — Deriv API

Esta pasta contém um espelho local verificável da documentação oficial da Deriv (`https://developers.deriv.com/llms.txt`), incluindo guias conceituais, referências de endpoints WebSocket/REST e schemas JSON.

## Estrutura
- `llms.txt` — Índice principal oficial da Deriv API.
- `llms/` — Documentos Markdown oficiais (autenticação, limites, erros, tipos de contrato, WebSocket público/demo/real, etc.).
- `schemas/` — Schemas JSON oficiais baixados a partir dos links referenciados.
- `manifest.json` — Manifesto com URLs originais, tamanhos, contagem e hashes SHA-256.
- `INTEGRATION_AUDIT.md` — Auditoria completa da integração do Prado Ubuntu HFT em relação à documentação oficial.

## Como atualizar
```bash
python scripts/sync_deriv_docs.py
```

## Como verificar integridade (SHA-256)
```bash
python scripts/sync_deriv_docs.py --verify
```
