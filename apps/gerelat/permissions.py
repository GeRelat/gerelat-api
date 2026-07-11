from rest_framework import permissions
from .models import EquipeProjeto

class IsOwnerOrTeamMember(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        projeto_do_relatorio = obj.evento.projeto

        #Lembrar de trocar para associação pelo user via foreign key depois, para evitar problemas de nomes duplicados e garantir integridade referencial.
        nome_usuario = request.user.get_full_name() or request.user.username

        return EquipeProjeto.objects.filter(
            projeto=projeto_do_relatorio,
            nome__iexact=nome_usuario 
        ).exists()