import logging

from celery import shared_task

from .models import Evento, ProjetoCampo, Relatorio, Template

logger = logging.getLogger(__name__)


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
) -> dict[str, str | int]:
    try:
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
        )

        return {
            "task_id": self.request.id,
            "id_relatorio": relatorio.id_relatorio,
        }
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
    stored_path: str,
    nome_template: str,
    programa_id: int,
    projeto_id: int | None,
) -> dict[str, str | int | None]:
    try:
        template = Template.objects.create(
            nome_template=nome_template,
            programa_id=programa_id,
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
