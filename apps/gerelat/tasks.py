import logging

from celery import shared_task

from .document_engine.variables import build_variables_context
from .models import Relatorio, Template

logger = logging.getLogger(__name__)


def _do_generate_relatorio(
    *,
    cliente_id: int | None = None,
    programa_id: int | None = None,
    projeto_id: int | None = None,
    evento_id: int | None = None,
    template_id: int,
    documento_json: dict | None = None,
    nome: str | None = None,
    task_id: str | None = None,
) -> dict:
    template = Template.objects.get(id=template_id)

    if documento_json is None:
        documento_json = template.modelo_json

    context = build_variables_context(
        cliente_id=cliente_id,
        programa_id=programa_id,
        projeto_id=projeto_id,
        evento_id=evento_id,
    )

    relatorio = Relatorio.objects.create(
        evento_id=evento_id,
        template_id=template_id,
        nome=nome or template.nome,
        arquivo_gerado="",
        status="SUCCESS",
        metadados=context,
        documento_json=documento_json or {},
    )

    return {
        "type": Relatorio.__name__,
        "id": relatorio.id,
    }


@shared_task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_relatorio(
    self,
    *,
    cliente_id: int | None = None,
    programa_id: int | None = None,
    projeto_id: int | None = None,
    evento_id: int | None = None,
    template_id: int,
    documento_json: dict | None = None,
    nome: str | None = None,
) -> dict:
    try:
        return _do_generate_relatorio(
            cliente_id=cliente_id,
            programa_id=programa_id,
            projeto_id=projeto_id,
            evento_id=evento_id,
            template_id=template_id,
            documento_json=documento_json,
            nome=nome,
            task_id=self.request.id,
        )
    except Exception:
        logger.exception("Falha ao gerar relatório.")
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
    nome: str,
    nivel: str,
    cliente_id: int | None = None,
    programa_id: int | None = None,
    projeto_id: int | None = None,
    modelo_json: dict,
) -> dict:
    try:
        template = Template.objects.create(
            nome=nome,
            nivel=nivel,
            cliente_id=cliente_id,
            programa_id=programa_id,
            projeto_id=projeto_id,
            modelo_json=modelo_json,
        )

        return {
            "type": Template.__name__,
            "id": template.id,
        }
    except Exception:
        logger.exception("Falha ao criar template.")
        raise
