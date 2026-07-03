import logging

from celery import shared_task

from .models import Evento, ProjetoCampo, Relatorio, Template

logger = logging.getLogger(__name__)


def _do_generate_relatorio(
    *,
    evento_id: int | None,
    template_id: int,
    documento_json: dict | None = None,
    task_id: str | None = None,
) -> dict:
    template = Template.objects.get(id_template=template_id)

    evento = None
    projeto_id = template.projeto_id
    if evento_id:
        evento = Evento.objects.select_related("projeto", "projeto__programa").get(
            id_evento=evento_id
        )
        projeto_id = evento.projeto_id

    if not projeto_id:
        raise ValueError("Projeto não encontrado para gerar relatório.")

    campos = ProjetoCampo.objects.filter(projeto_id=projeto_id)
    context = {campo.referencia: campo.valor for campo in campos}

    relatorio = Relatorio.objects.create(
        evento_id=evento.id_evento if evento else None,
        template_id=template_id,
        nome=template.nome_template,
        arquivo_gerado="",
        status="SUCCESS",
        metadados=context,
        documento_json=documento_json or {},
    )

    return {"task_id": task_id, "id_relatorio": relatorio.id_relatorio}


@shared_task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_relatorio(
    self,
    *,
    evento_id: int | None,
    template_id: int,
    documento_json: dict | None = None,
) -> dict:
    try:
        return _do_generate_relatorio(
            evento_id=evento_id,
            template_id=template_id,
            documento_json=documento_json,
            task_id=self.request.id,
        )
    except Exception:
        logger.exception("Falha ao gerar relatório.")
        raise


def generate_relatorio_sync(
    *,
    evento_id: int | None,
    template_id: int,
    documento_json: dict | None = None,
) -> dict:
    """Versão síncrona — não requer Celery."""
    try:
        return _do_generate_relatorio(
            evento_id=evento_id,
            template_id=template_id,
            documento_json=documento_json,
        )
    except Exception:
        logger.exception("Falha ao gerar relatório (sync).")
        raise


@shared_task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def create_template(
    self,
    *,
    stored_path: str,
    nome_template: str,
    projeto_id: int,
) -> dict:
    try:
        template = Template.objects.create(
            nome_template=nome_template,
            projeto_id=projeto_id,
            modelo_arquivo_base=stored_path,
        )

        return {
            "task_id": self.request.id,
            "id_template": template.id_template,
            "nome_template": template.nome_template,
            "modelo_arquivo_base": template.modelo_arquivo_base,
        }
    except Exception:
        logger.exception("Falha ao criar template.")
        raise
