from django.utils.deprecation import MiddlewareMixin

class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            from apps.gerelat.models import AuditLog 
            
            usuario = request.user if request.user.is_authenticated else None
            
            AuditLog.objects.create(
                usuario=usuario,
                acao=request.method,
                endpoint=request.path
            )