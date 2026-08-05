from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """Exception handler customizado do DRF.

    O DRF só converte `APIException`/`Http404`/`PermissionDenied` em resposta
    HTTP; qualquer outra exceção sobe crua e vira 500. `ProtectedError` é
    levantada pelo Django ao tentar excluir um registro referenciado por uma
    FK com `on_delete=PROTECT` (ex.: `Relatorio.template`, `Programa.cliente`)
    — aqui ela vira uma resposta 409 com mensagem legível, em vez do 500
    genérico.
    """
    if isinstance(exc, ProtectedError):
        protegidos = list(exc.protected_objects)
        if protegidos:
            modelo = protegidos[0]._meta.verbose_name_plural
            detail = f"Não é possível excluir: existem {modelo} vinculados a este item."
        else:
            detail = "Não é possível excluir: existem registros vinculados a este item."
        return Response({"detail": detail}, status=status.HTTP_409_CONFLICT)

    return drf_exception_handler(exc, context)
