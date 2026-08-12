from __future__ import annotations

import json
import logging
from datetime import time
from typing import TYPE_CHECKING

from django.conf import settings

from .recurrence import dia_semana_para_cron_weekday

if TYPE_CHECKING:
    from ...models import AgendamentoRelatorio

logger = logging.getLogger(__name__)


def sincronizar_periodic_task(agendamento: AgendamentoRelatorio) -> None:
    """Cria/atualiza a `PeriodicTask` do django-celery-beat associada ao
    `agendamento`, para que ela reflita fielmente seu tipo (pontual/
    recorrente), recorrência, horário e status ativo/inativo.

    Deve ser chamado explicitamente após persistir o agendamento (não é
    acionado automaticamente por `save()`). Não faz nada se `agendamento`
    ainda não tiver sido persistido (`id` ausente).
    """
    if not agendamento.id:
        return

    from ...models import AgendamentoRelatorio

    try:
        from django_celery_beat.models import (
            ClockedSchedule,
            CrontabSchedule,
            PeriodicTask,
        )
    except Exception:
        logger.exception("django_celery_beat não disponível")
        return

    task_name = f"agendamento_relatorio_{agendamento.id}"
    task_func = "apps.gerelat.tasks.executar_agendamento_relatorio"
    task_kwargs = json.dumps({"agendamento_id": agendamento.id})

    clocked_schedule = None
    crontab_schedule = None
    one_off = False

    if agendamento.tipo_agendamento == AgendamentoRelatorio.TIPO_PONTUAL:
        if agendamento.data_hora_execucao:
            try:
                clocked_schedule, _ = ClockedSchedule.objects.get_or_create(
                    clocked_time=agendamento.data_hora_execucao,
                )
                one_off = True
            except Exception:
                logger.exception(
                    f"Erro ao obter/criar ClockedSchedule para AgendamentoRelatorio {agendamento.id}"
                )
    elif agendamento.tipo_agendamento == AgendamentoRelatorio.TIPO_RECORRENTE:
        horario = agendamento.horario_execucao or time(8, 0)
        minute = str(horario.minute)
        hour = str(horario.hour)
        month_of_year = "*"
        day_of_week = "*"
        day_of_month = "*"

        if agendamento.recorrencia == AgendamentoRelatorio.RECORRENCIA_SEMANAL:
            w = agendamento.dia_semana if agendamento.dia_semana is not None else 1
            day_of_week = dia_semana_para_cron_weekday(w)
        elif agendamento.recorrencia == AgendamentoRelatorio.RECORRENCIA_MENSAL:
            target_day = agendamento.dia_mes or 1
            if target_day > 28:
                if agendamento.proxima_execucao:
                    try:
                        clocked_schedule, _ = ClockedSchedule.objects.get_or_create(
                            clocked_time=agendamento.proxima_execucao,
                        )
                    except Exception:
                        logger.exception(
                            f"Erro ao obter/criar ClockedSchedule para AgendamentoRelatorio {agendamento.id}"
                        )
            else:
                day_of_month = str(target_day)

        if clocked_schedule is None:
            tz_str = getattr(settings, "TIME_ZONE", "America/Sao_Paulo")
            try:
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=minute,
                    hour=hour,
                    day_of_week=day_of_week,
                    day_of_month=day_of_month,
                    month_of_year=month_of_year,
                    timezone=tz_str,
                )
            except Exception:
                logger.exception(
                    f"Erro ao obter/criar CrontabSchedule para AgendamentoRelatorio {agendamento.id}"
                )
        else:
            one_off = True

    try:
        if agendamento.periodic_task_id:
            pt = agendamento.periodic_task
            pt.name = task_name
            pt.task = task_func
            pt.kwargs = task_kwargs
            pt.enabled = agendamento.ativo
            pt.one_off = one_off
            pt.clocked = clocked_schedule
            pt.crontab = crontab_schedule
            pt.save()
        else:
            pt = PeriodicTask.objects.create(
                name=task_name,
                task=task_func,
                kwargs=task_kwargs,
                enabled=agendamento.ativo,
                one_off=one_off,
                clocked=clocked_schedule,
                crontab=crontab_schedule,
            )
            agendamento.periodic_task = pt
            AgendamentoRelatorio.objects.filter(id=agendamento.id).update(
                periodic_task=pt
            )
    except Exception:
        logger.exception(
            f"Falha ao sincronizar PeriodicTask para AgendamentoRelatorio {agendamento.id}"
        )


def remover_periodic_task(agendamento_id: int, periodic_task) -> None:
    """Remove a `PeriodicTask` de um agendamento excluído e, se o
    `ClockedSchedule` associado não for mais referenciado por nenhuma outra
    `PeriodicTask`, remove também o schedule órfão.
    """
    if not periodic_task:
        return

    clocked = periodic_task.clocked
    try:
        periodic_task.delete()
        if clocked and not clocked.periodictask_set.exists():
            clocked.delete()
    except Exception:
        logger.exception(
            f"Erro ao deletar PeriodicTask/ClockedSchedule para AgendamentoRelatorio {agendamento_id}"
        )
