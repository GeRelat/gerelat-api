# Guia de Testes — GeRelat

## Pré-requisitos

- Docker rodando (PostgreSQL + Redis)
- `uv` instalado

---

## 1. Subir os serviços

```bash
# Banco de dados e Redis
docker compose up -d 

---

## 2. Frontend

```bash
cd ../prosemirror-doc-editor
npm run dev
```

Acesse: **http://localhost:5175** (porta pode variar, ver output do Vite)

---

## 3. Login e Token JWT

### Via Swagger (recomendado)

1. Abra **http://localhost:8000/docs/**
2. Encontre `POST /auth/login/`
3. Clique em **Try it out** e envie:

```json
{
  "email": "admin@gerelat.dev",
  "password": "admin123"
}
```

4. Copie o valor do campo `access` da resposta.

## 4. Configurar o Frontend

1. Abra o editor no browser
2. Vá na aba **✏️ Template** → painel lateral → aba **⚙️ Config**
3. Preencha:
   - **URL da API:** `http://localhost:8000`
   - **Token JWT:** cole o valor `access` obtido no passo 3
   - **ID do Projeto:** `1`
4. Clique **Salvar**

---

## 5. Dados de teste disponíveis

Já foram criados no banco:

| Entidade         | ID  | Nome                            |
| ---------------- | --- | ------------------------------- |
| Cliente          | 1   | Prefeitura Municipal de Exemplo |
| Programa         | 1   | Programa Social Inclusão        |
| Projeto          | 1   | Capacitação Profissional 2026   |
| Classe de Evento | 1   | Oficina de Capacitação          |
| Evento           | 1   | Oficina de Informática Básica   |

### Variáveis disponíveis (projeto 1)

| Referência            | Tipo     | Valor de exemplo                                    |
| --------------------- | -------- | --------------------------------------------------- |
| `nome_evento`         | text     | Oficina de Informática Básica                       |
| `data_evento`         | text     | 20 de junho de 2026                                 |
| `local_evento`        | text     | Centro Comunitário Vila Nova                        |
| `endereco_evento`     | text     | Rua das Flores, 100 — Vila Nova                     |
| `carga_horaria`       | text     | 8 horas                                             |
| `numero_contrato`     | text     | CONT-2026-001                                       |
| `nome_coordenador`    | text     | Dr. Carlos Mendes                                   |
| `cargo_coordenador`   | text     | Coordenador Geral                                   |
| `nome_parceira`       | text     | Instituto Futuro                                    |
| `total_participantes` | text     | 32 participantes                                    |
| `objetivo_evento`     | richtext | Texto com heading e negrito                         |
| `metodologia`         | richtext | Dois parágrafos formatados                          |
| `conclusao`           | richtext | Parágrafo com negrito e itálico                     |
| `lista_participantes` | table    | 5 participantes (nome, CPF, faixa etária, presença) |
| `equipe_execucao`     | table    | 2 membros da equipe (nome, cargo, CH)               |

---

## 6. Criar um Template

### Opção A — Carregar o template de exemplo no editor

1. No editor, vá na aba lateral **⬆ Import**
2. Abra o arquivo `template_exemplo.json` na raiz do repositório `gerelat-api`
3. Copie o conteúdo e cole na textarea
4. Clique **⬆ Carregar documento**
5. O template aparece no editor com todos os placeholders visíveis

### Opção B — Construir no editor manualmente

Use os botões da toolbar:
- **⟨⟩ Variável** — insere um placeholder inline (ex.: `nome_evento`)
- **📝 Bloco** — insere um bloco de texto editável (ex.: `objetivo_evento`)
- **📊 Tabela** — insere referência de tabela (ex.: `lista_participantes`)
- **🖼️ Imagem** — insere referência de imagem

### Opção C — Converter um DOCX existente

1. Aba **⚙️ Config** → **📂 Carregar DOCX no Editor**
2. Selecione um arquivo `.docx`
3. O conteúdo é convertido para ProseMirror e carregado no editor

### Salvar o template na API

1. Aba **⚙️ Config** → campo **Nome do Template** → ex.: `Relatório de Atividade`
2. Clique **💾 Salvar JSON como Template**
3. O ID do template criado aparece automaticamente no campo abaixo

---

## 7. Gerar um Relatório

1. Vá na aba **📄 Relatórios**
2. Selecione o template criado no passo 6
3. Opcionalmente informe o **ID do Evento** (`1`)
4. Clique **👁 Visualizar Preview**

O painel direito exibe o documento com todas as variáveis preenchidas.

5. Edite os blocos destacados em azul (`📝 texto personalizado`) se necessário
   - Use **B / I / U** na toolbar do preview para formatar
   - O restante do documento está bloqueado para edição
6. Clique **✅ Gerar Relatório Definitivo**
7. O relatório aparece na lista à esquerda com status `SUCCESS`
8. Clique **⬇ Baixar DOCX** para baixar o arquivo gerado

---

## 8. Gerenciar Variáveis

1. Vá na aba **⟨⟩ Variáveis**
2. As 15 variáveis do projeto já estão listadas
3. Para adicionar: preencha **Referência**, **Tipo** e **Valor** → **Adicionar**
4. Para editar: clique **✏️ Editar** em qualquer variável
5. Para excluir: clique **🗑️**

> A referência deve corresponder exatamente ao placeholder usado no template.

---

## 9. Testar via API diretamente

Com o token em mãos, todos os endpoints podem ser testados via Swagger em **http://localhost:8000/docs/**.

Clique em **Authorize** no topo do Swagger e informe:
```
Bearer eyJ...seu_token_access...
```

### Endpoints principais

| Método | Endpoint                     | Descrição                         |
| ------ | ---------------------------- | --------------------------------- |
| `POST` | `/auth/login/`               | Obter token JWT                   |
| `GET`  | `/projeto-campos/?projeto=1` | Listar variáveis                  |
| `POST` | `/projeto-campos/`           | Criar variável                    |
| `GET`  | `/templates/`                | Listar templates                  |
| `POST` | `/templates/from-json/`      | Criar template via JSON           |
| `GET`  | `/templates/{id}/preview/`   | Preview com variáveis resolvidas  |
| `POST` | `/templates/convert-docx/`   | Converter DOCX → ProseMirror JSON |
| `POST` | `/relatorios/gerar/`         | Gerar relatório                   |
| `GET`  | `/relatorios/{id}/download/` | Baixar DOCX gerado                |

---

## 10. Problemas comuns

**Token expirado**
```
{"detail": "Given token not valid for any token type"}
```
→ Repita o login e atualize o token no campo Config do editor.

**Celery não está rodando**
O relatório fica em status `PENDING` indefinidamente.
→ Inicie o worker: `uv run celery -A config worker --loglevel=warning`

**Template sem `modelo_json`**
```
{"detail": "Template não possui modelo_json."}
```
→ O template foi criado via upload de `.docx` antigo. Use o editor para criar um novo via **Salvar JSON como Template**.

**Variável não substituída no DOCX**
→ Verifique se a `referência` da variável bate exatamente com o atributo `ref` do nodo no template (sem espaços, sem acentos).
