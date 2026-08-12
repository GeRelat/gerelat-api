from django.db.models import Q

from ..models import CampoDefinicao


def resolver_campos_definicao_escopo(cliente=None, programa=None, projeto=None):
    """
    Retorna o queryset de CampoDefinicao visível para um Template/Relatório
    criado no nível informado (exatamente um entre cliente/programa/projeto
    deve ser passado, seguindo a mesma regra de nível único do Template).
    """
    if projeto:
        return _escopo_projeto(projeto)
    if programa:
        return _escopo_programa(programa)
    if cliente:
        return _escopo_cliente(cliente)
    return CampoDefinicao.objects.none()


def _escopo_projeto(projeto):
    """
    Projeto: sobe a árvore. Caminho único e fixo — o próprio Projeto,
    o Programa pai, o Cliente avô. Sem fan-out.
    """
    return CampoDefinicao.objects.filter(
        Q(projeto=projeto)
        | Q(programa=projeto.programa)
        | Q(cliente=projeto.programa.cliente)
    )


def _escopo_programa(programa):
    """
    Programa: 1 nível ancestral (o Cliente pai) + o próprio Programa.
    Sem fan-out para projetos descendentes.
    """
    return CampoDefinicao.objects.filter(
        Q(programa=programa) | Q(cliente=programa.cliente)
    )


def _escopo_cliente(cliente):
    """
    Cliente: é a raiz. No momento, o escopo do cliente expõe apenas as variáveis
    customizadas criadas no próprio nível do Cliente (sem fan-out para programas
    ou projetos descendentes).
    """
    return CampoDefinicao.objects.filter(cliente=cliente)
