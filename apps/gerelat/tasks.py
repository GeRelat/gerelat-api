import logging

from celery import shared_task

from .models import Evento, ProjetoCampo, Relatorio, Template

logger = logging.getLogger(__name__)


def _do_generate_relatorio(
    *,
    evento_id: int | None,
    template_id: int,
    documento_json: dict | None = None,
    nome: str | None = None,
    task_id: str | None = None,
) -> dict:
    template = Template.objects.get(id=template_id)

    evento = None
    projeto_id = template.projeto_id
    if evento_id:
        evento = Evento.objects.select_related("projeto", "projeto__programa").get(
            id_evento=evento_id
        )
        projeto_id = evento.projeto_id

    if not projeto_id:
        raise ValueError("Projeto não encontrado para gerar relatório.")

    if documento_json is None:
        documento_json = Template.objects.get(id=template_id).modelo_json

    campos = ProjetoCampo.objects.filter(projeto_id=projeto_id)
    context = {campo.referencia: campo.valor for campo in campos}

    relatorio = Relatorio.objects.create(
        evento_id=evento.id if evento else None,
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
    evento_id: int | None,
    template_id: int,
    documento_json: dict | None = None,
    nome: str | None = None,
) -> dict:
    try:
        return _do_generate_relatorio(
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
    projeto_id: int,
    modelo_json: dict,
) -> dict:
    try:
        template = Template.objects.create(
            nome=nome,
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
