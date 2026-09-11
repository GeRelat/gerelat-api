import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .document_engine.converters import replace_placeholders
from .document_engine.variables import build_variables_context
from .models import AgendamentoRelatorio, Evento, Relatorio, Template
from .services.agendamento_relatorio import sincronizar_periodic_task
from .services.assinaturas_relatorio import resolver_assinaturas

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
    assinaturas: list[dict] | None = None,
    task_id: str | None = None,
) -> dict:
    template = Template.objects.get(id=template_id)

    context = build_variables_context(
        cliente_id=cliente_id,
        programa_id=programa_id,
        projeto_id=projeto_id,
        evento_id=evento_id,
    )

    # Assinaturas congeladas no metadados (o download não tem escopo para
    # re-resolver). Sem override, usa as do template.
    context["sistema.assinaturas"] = resolver_assinaturas(
        template_id, assinaturas_override=assinaturas
    )

    # Sem documento_json explícito (ex.: relatório agendado), resolve as
    # variáveis do template agora. Guardar o template cru aqui faria o download
    # (que prioriza relatorio.documento_json) baixar o template sem substituir
    # nenhuma variável.
    if documento_json is None and template.modelo_json:
        documento_json = replace_placeholders(template.modelo_json, context)

    if projeto_id is None and evento_id is not None:
        try:
            ev = Evento.objects.select_related("projeto").get(id=evento_id)
            if ev.projeto_id:
                projeto_id = ev.projeto_id
        except Evento.DoesNotExist:
            pass

    if projeto_id is None and template.projeto_id is not None:
        projeto_id = template.projeto_id

    if projeto_id is None:
        raise ValueError("projeto_id é obrigatório para gerar o relatório.")

    relatorio = Relatorio.objects.create(
        projeto_id=projeto_id,
        evento_id=evento_id,
        template_id=template_id,
        nome=nome or template.nome,
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
    assinaturas: list[dict] | None = None,
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
            assinaturas=assinaturas,
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


@shared_task
def executar_agendamento_relatorio(agendamento_id: int) -> dict | None:
    now = timezone.now()
    with transaction.atomic():
        try:
            agendamento = AgendamentoRelatorio.objects.select_for_update(
                skip_locked=True
            ).get(id=agendamento_id)
        except AgendamentoRelatorio.DoesNotExist:
            logger.info(f"Agendamento {agendamento_id} não disponível para execução.")
            return None

        if not agendamento.ativo:
            return None

        if agendamento.ultima_execucao:
            diff = (now - agendamento.ultima_execucao).total_seconds()
            if diff < 10:
                logger.info(
                    f"Agendamento {agendamento_id} já executado há {diff:.1f}s."
                )
                return None

        cliente_id = agendamento.cliente_id
        programa_id = agendamento.programa_id
        projeto_id = agendamento.projeto_id
        evento_id = agendamento.evento_id
        template_id = agendamento.template_id
        documento_json = agendamento.documento_json or None
        nome = agendamento.nome

        agendamento.ultima_execucao = now
        if agendamento.tipo_agendamento == AgendamentoRelatorio.TIPO_PONTUAL:
            agendamento.ativo = False
            agendamento.proxima_execucao = None
        else:
            agendamento.proxima_execucao = agendamento.calcular_proxima_execucao(
                a_partir_de=agendamento.proxima_execucao or now
            )

        agendamento.save(recalculate_proxima=False)

        sincronizar_periodic_task(agendamento)

    generate_relatorio.delay(
        cliente_id=cliente_id,
        programa_id=programa_id,
        projeto_id=projeto_id,
        evento_id=evento_id,
        template_id=template_id,
        documento_json=documento_json,
        nome=nome,
    )

    return None
