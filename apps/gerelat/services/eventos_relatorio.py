from rest_framework.exceptions import ValidationError

from ..models import Evento, TemplateClasseEvento


def eventos_disponiveis_para_relatorio(template):
    """
    Retorna os Eventos elegíveis para gerar um Relatório a partir deste Template:
    pertencentes ao escopo do Template + classe_evento dentre as associadas ao Template (se houver).
    """
    classes_ids = list(
        TemplateClasseEvento.objects.filter(template=template).values_list(
            "classe_evento_id", flat=True
        )
    )

    if classes_ids:
        qs = Evento.objects.filter(classe_evento_id__in=classes_ids)
    else:
        qs = Evento.objects.all()

    if template.projeto_id:
        qs = qs.filter(projeto_id=template.projeto_id)
    elif template.programa_id:
        qs = qs.filter(projeto__programa_id=template.programa_id)
    elif template.cliente_id:
        qs = qs.filter(projeto__programa__cliente_id=template.cliente_id)
    else:
        return Evento.objects.none()

    return qs.distinct()


def validar_classe_evento_mesmo_escopo(template, classe_evento):
    if template.programa_id:
        if classe_evento.programa_id != template.programa_id:
            raise ValidationError(
                "A Classe de Evento associada deve pertencer ao mesmo Programa do Template."
            )
    elif template.projeto_id:
        if classe_evento.programa_id != template.projeto.programa_id:
            raise ValidationError(
                "A Classe de Evento associada deve pertencer ao Programa do Projeto do Template."
            )
    elif template.cliente_id:
        if classe_evento.programa.cliente_id != template.cliente_id:
            raise ValidationError(
                "A Classe de Evento associada deve pertencer ao Cliente do Template."
            )
    else:
        raise ValidationError("Template sem escopo válido.")
