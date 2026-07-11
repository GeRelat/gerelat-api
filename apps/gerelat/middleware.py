from django.utils.deprecation import MiddlewareMixin

class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Filtramos para logar apenas ações que modificam o banco (ignora requisições GET/Leitura)
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Importação local para evitar erro de inicialização cíclica no Django
            from apps.gerelat.models import AuditLog 
            
            # Pega o usuário se ele estiver autenticado
            usuario = request.user if request.user.is_authenticated else None
            
            # Cria o registro na tabela de auditoria
            AuditLog.objects.create(
                usuario=usuario,
                acao=request.method,
                endpoint=request.path
            )