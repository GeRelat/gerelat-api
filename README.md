## 🛠️ GeRelat - API

### 1. Criar ambiente virtual

```bash
uv venv
```

---

### 2. Instalar dependências

#### Produção + desenvolvimento:

```bash
uv sync
```

#### Apenas produção:

```bash
uv sync --no-dev
```

---

### 3. Adicionar dependências

#### Dependência de produção:

```bash
uv add <pacote>
```

Exemplo:

```bash
uv add docxtpl
```

---

#### Dependência de desenvolvimento:

```bash
uv add --dev <pacote>
```

Exemplo:

```bash
uv add --dev ruff pyright
```

---

### 4. Remover dependências

```bash
uv remove <pacote>
```

---

### 5. Atualizar dependências

```bash
uv lock --upgrade
uv sync
```

---

### 6. Copiar .env.example para .env


### 7. Rodar projeto Django (PostgreSQL necessário)

```bash
uv run manage.py runserver
```
ou

```bash
uv run granian config.asgi:application --interface asginl
```

---

### 7.1. Migrations

Criar migrations:

```bash
uv run manage.py makemigrations
```

Aplicar migrations:

```bash
uv run manage.py migrate
```

---

### 8. Docker com Django e PostgreSQL

#### 8.1 Subir os containers (build + execução)

```bash
docker compose up --build
```

Para rodar em segundo plano:

```bash
docker compose up -d --build
```

Para subir somente o banco (PostgreSQL):

```bash
docker compose up -d db
```

#### 8.2 Acessar a aplicação

- API: http://127.0.0.1:8000/
- Documentação Swagger: http://127.0.0.1:8000/docs/
- Healthcheck: http://127.0.0.1:8000/health/
- Flower (monitoramento Celery): http://127.0.0.1:5555/


#### 8.3 Parar os containers

```bash
docker compose down
```

Parar e remover também o volume do PostgreSQL:

```bash
docker compose down -v
```

Para parar somente o banco (PostgreSQL):

```bash
docker compose stop db
```

Para parar os serviços assíncronos (Celery/Redis/Flower):

```bash
docker compose stop worker redis flower
```

---

### 9. Executar ferramentas de qualidade (Extras)

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
