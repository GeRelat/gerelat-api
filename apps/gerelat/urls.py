from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import upload_imagem_editor, healthcheck
from . import views

app_name = "gerelat"
router = DefaultRouter()
router.register(r"programas", views.ProgramaViewSet)
router.register(r"programa-campos", views.ProgramaCampoViewSet)
router.register(r"equipes-programa", views.EquipeProgramaViewSet)
router.register(r"projetos", views.ProjetoViewSet)
router.register(r"projeto-campos", views.ProjetoCampoViewSet)
router.register(r"equipes-projeto", views.EquipeProjetoViewSet)
router.register(r"classes-evento", views.ClasseEventoViewSet)
router.register(r"eventos", views.EventoViewSet)
router.register(r"templates", views.TemplateViewSet)
router.register(r"template-classes-evento", views.TemplateClasseEventoViewSet)
router.register(r"relatorios", views.RelatorioViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path('upload-imagem/', upload_imagem_editor, name='upload-imagem-editor'),
    path('health/', healthcheck, name='healthcheck'),
]
