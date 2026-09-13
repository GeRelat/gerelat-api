## 🛠️ GeRelat - API

### 1. Criar ambiente virtual

```bash
uv venv
```
---

### 2. Instalar dependências

```bash
uv sync
```
---

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

> **Nota:** No arquivo `.env`, configure:
> - `DJANGO_DB_HOST=db` se estiver rodando via **Docker**.
> - `DJANGO_DB_HOST=localhost` se estiver executando comandos **localmente**.

---

### 4. Migrations

Criar migrations:

```bash
uv run manage.py makemigrations
```

Aplicar migrations:

```bash
uv run manage.py migrate
```

---

### 5. Criar usuário administrador

Cria o superusuário inicial com o vínculo necessário em `MembroGeRelat`:

```bash
uv run manage.py create_admin --email admin@gerelat.tech --password admin123
```

*(Ou via Docker: `docker compose exec web uv run manage.py create_admin`)*

---

### 6. Execução local

#### 6.1 Subir serviços de apoio (PostgreSQL e Redis)

```bash
docker compose up -d db redis
```

#### 6.2 Rodar a API Django

```bash
uv run manage.py runserver
```

#### 6.3 Rodar Celery (em terminais separados)

Worker:
```bash
uv run celery -A config worker --loglevel=info
```

Beat (tarefas periódicas):
```bash
uv run celery -A config beat -l info
```

---

### 7. Execução completa via Docker

#### 7.1 Subir todos os containers (build + execução)

```bash
docker compose up --build
```

Para rodar em segundo plano:

```bash
docker compose up -d --build
```

#### 7.2 Acessar a aplicação

- **API:** http://127.0.0.1:8000/
- **Django Admin:** http://127.0.0.1:8000/admin/
- **Documentação Swagger:** http://127.0.0.1:8000/docs/
- **OpenAPI Schema:** http://127.0.0.1:8000/schema/
- **Silk (Profiler de queries/requests):** http://127.0.0.1:8000/silk/
- **Healthcheck:** http://127.0.0.1:8000/health/
- **Flower (monitoramento Celery):** http://127.0.0.1:5555/

#### 7.3 Parar os containers

```bash
docker compose down
```

Parar e remover volumes (banco de dados):

```bash
docker compose down -v
```

---

### 8. Ferramentas de qualidade e testes

#### Testes automatizados

```bash
uv run manage.py test
```

#### Lint

```bash
uv run ruff check .
```

#### Formatação

```bash
uv run ruff format .
```

#### Tipagem

```bash
uv run pyright
```
