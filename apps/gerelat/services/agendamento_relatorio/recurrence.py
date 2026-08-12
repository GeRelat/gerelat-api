from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from ...models import AgendamentoRelatorio


def dia_semana_para_python_weekday(dia_semana: int) -> int:
    """Schema interno 1–7 (1=Seg...7=Dom) -> Python weekday() (0=Seg...6=Dom)."""
    return (dia_semana - 1) % 7


def dia_semana_para_cron_weekday(dia_semana: int) -> str:
    """Schema interno 1–7 (1=Seg...7=Dom) -> cron day_of_week (0=Dom...6=Sab)."""
    return str(dia_semana % 7)


def calcular_proxima_execucao(agendamento: AgendamentoRelatorio, a_partir_de=None):
    """Calcula a próxima data/hora de execução de `agendamento` a partir de
    `a_partir_de` (ou de `agendamento.ultima_execucao`, ou de `timezone.now()`,
    na ordem de precedência).

    Regras:
    - Pontual: retorna `data_hora_execucao` se ainda não foi executado (ou se
      a data de execução for posterior à última execução registrada); caso
      contrário, `None`.
    - Recorrente diário/semanal/mensal: calcula a próxima ocorrência a partir
      de `horario_execucao` e, quando aplicável, `dia_semana`/`dia_mes`.
      Para recorrência mensal, dias que não existem no mês de destino (ex.:
      31 em abril) são ajustados para o último dia daquele mês.
    """
    from ...models import AgendamentoRelatorio

    referencia = a_partir_de or agendamento.ultima_execucao or timezone.now()

    if agendamento.tipo_agendamento == AgendamentoRelatorio.TIPO_PONTUAL:
        if agendamento.data_hora_execucao and (
            agendamento.ultima_execucao is None
            or agendamento.data_hora_execucao > agendamento.ultima_execucao
        ):
            return agendamento.data_hora_execucao
        return None

    if agendamento.tipo_agendamento == AgendamentoRelatorio.TIPO_RECORRENTE:
        horario = agendamento.horario_execucao or time(8, 0)
        tz = timezone.get_current_timezone()

        if agendamento.recorrencia == AgendamentoRelatorio.RECORRENCIA_DIARIO:
            ref_dt = referencia.astimezone(tz)
            candidate_dt = timezone.make_aware(
                datetime.combine(ref_dt.date(), horario), tz
            )
            if candidate_dt <= ref_dt:
                candidate_dt += timedelta(days=1)
            return candidate_dt

        elif agendamento.recorrencia == AgendamentoRelatorio.RECORRENCIA_SEMANAL:
            w = agendamento.dia_semana if agendamento.dia_semana is not None else 1
            target_w = dia_semana_para_python_weekday(w)

            ref_dt = referencia.astimezone(tz)
            candidate_date = ref_dt.date()
            days_ahead = (target_w - candidate_date.weekday()) % 7
            candidate_dt = timezone.make_aware(
                datetime.combine(candidate_date + timedelta(days=days_ahead), horario),
                tz,
            )
            if candidate_dt <= ref_dt:
                candidate_dt += timedelta(days=7)
            return candidate_dt

        elif agendamento.recorrencia == AgendamentoRelatorio.RECORRENCIA_MENSAL:
            target_day = agendamento.dia_mes or 1
            ref_dt = referencia.astimezone(tz)
            year = ref_dt.year
            month = ref_dt.month

            def _get_datetime(y, m, d):
                max_d = calendar.monthrange(y, m)[1]
                valid_d = min(d, max_d)
                return timezone.make_aware(
                    datetime(
                        y, m, valid_d, horario.hour, horario.minute, horario.second
                    ),
                    tz,
                )

            candidate_dt = _get_datetime(year, month, target_day)
            if candidate_dt <= ref_dt:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                candidate_dt = _get_datetime(year, month, target_day)

            return candidate_dt

    return None
