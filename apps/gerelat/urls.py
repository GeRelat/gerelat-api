from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "gerelat"
router = DefaultRouter()
router.register(r"assets", views.AssetViewSet)
router.register(r"clientes", views.ClienteViewSet)
router.register(r"programas", views.ProgramaViewSet)
router.register(r"equipes-programa", views.EquipeProgramaViewSet)
router.register(r"projetos", views.ProjetoViewSet)
router.register(r"campo-definicoes", views.CampoDefinicaoViewSet)
router.register(r"campo-valores", views.CampoValorViewSet)
router.register(r"equipes-projeto", views.EquipeProjetoViewSet)
router.register(r"classes-evento", views.ClasseEventoViewSet)
router.register(r"eventos", views.EventoViewSet)
router.register(r"templates", views.TemplateViewSet)
router.register(r"template-classes-evento", views.TemplateClasseEventoViewSet)
router.register(r"assinaturas-template", views.AssinaturaTemplateViewSet)
router.register(r"relatorios", views.RelatorioViewSet)
router.register(
    r"agendamentos-relatorio",
    views.AgendamentoRelatorioViewSet,
    basename="agendamento-relatorio",
)
router.register(r"tasks", views.TaskViewSet, basename="tasks")
# Autorização
router.register(
    r"membros-gerelat", views.MembroGeRelatViewSet, basename="membros-gerelat"
)
router.register(
    r"membros-cliente", views.MembroClienteViewSet, basename="membros-cliente"
)
router.register(
    r"solicitacoes-cliente",
    views.SolicitacaoClienteViewSet,
    basename="solicitacoes-cliente",
)
router.register(
    r"membros-programa", views.MembroProgramaViewSet, basename="membros-programa"
)
router.register(
    r"membros-projeto", views.MembroProjetoViewSet, basename="membros-projeto"
)

urlpatterns = [
    path(
        "dashboard/resumo/",
        views.DashboardResumoView.as_view(),
        name="dashboard-resumo",
    ),
    path(
        "programas/<int:programa_id>/membros/",
        views.AdicionarMembroProgramaView.as_view(),
        name="adicionar-membro-programa",
    ),
    path(
        "programas/<int:programa_id>/projetos/<int:projeto_id>/membros/",
        views.AdicionarMembroProjetoView.as_view(),
        name="adicionar-membro-projeto",
    ),
    path("", include(router.urls)),
]
