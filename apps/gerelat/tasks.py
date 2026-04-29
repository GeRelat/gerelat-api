import logging

from celery import shared_task
from docxtpl import DocxTemplate

from .models import Template

logger = logging.getLogger(__name__)


@shared_task
def task_relatorio_exemplo(data):
    doc = DocxTemplate(data["template_path"])

    context = {
        "empresa": "BRISA",
        "parceira": "FURG",
        "assunto": "Acompanhamento da execução do Projeto",
        "data": "13/03/2026",
        "horario": "16h - 17h",
        "coord_local": {"nome": "João Silva", "funcao": "Coordenador Local Geral"},
    }
    doc.render(context)
    doc.save(data["output_path"])


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
