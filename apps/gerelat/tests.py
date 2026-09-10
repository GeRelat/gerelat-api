from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.gerelat.enums import CampoTipo, NivelAplicacao, NivelTemplate
from apps.gerelat.models import (
    AgendamentoRelatorio,
    Asset,
    AssetUso,
    AssinaturaTemplate,
    CampoDefinicao,
    CampoValor,
    ClasseEvento,
    Cliente,
    EquipePrograma,
    EquipeProjeto,
    Evento,
    MembroCliente,
    MembroGeRelat,
    MembroPrograma,
    MembroProjeto,
    Programa,
    Projeto,
    Relatorio,
    Template,
    TemplateClasseEvento,
)
from apps.gerelat.permissions import PodeAcessarProjeto
from apps.gerelat.serializers import (
    AgendamentoRelatorioSerializer,
    ClienteSerializer,
    TemplateClasseEventoSerializer,
)
from apps.gerelat.services.agendamento_relatorio import (
    dia_semana_para_cron_weekday,
    dia_semana_para_python_weekday,
    remover_periodic_task,
    sincronizar_periodic_task,
)
from apps.gerelat.services.autorizacao import get_nivel_acesso
from apps.gerelat.services.eventos_relatorio import (
    eventos_disponiveis_para_relatorio,
    validar_classe_evento_mesmo_escopo,
)
from apps.gerelat.services.gestao_acesso import (
    ConflitoDeAcessoError,
    adicionar_membro_programa,
    adicionar_membro_projeto,
)
from apps.gerelat.services.variaveis_escopo import resolver_campos_definicao_escopo

User = get_user_model()


class GestaoAcessoTest(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome="Cliente Teste",
            cnpj="00000000000000",
            nome_contato="Contato",
            email_contato="c@c.com",
            fone_contato="00000",
            numero_contrato="123",
            data_termino_contrato="2030-01-01",
        )
        self.programa = Programa.objects.create(
            nome="Programa Teste", cliente=self.cliente
        )
        self.projeto = Projeto.objects.create(
            nome="Projeto Teste", programa=self.programa
        )
        self.user = User.objects.create_user(
            email="user@test.com", password="password123", full_name="User Test"
        )

    def test_adicionar_sem_conflito_funciona_direto(self):
        adicionar_membro_projeto(self.user, self.projeto)
        self.assertTrue(
            MembroProjeto.objects.filter(user=self.user, projeto=self.projeto).exists()
        )
        self.assertEqual(get_nivel_acesso(self.user, self.projeto), "membro_projeto")

    def test_promocao_remove_membro_projeto_redundante(self):
        adicionar_membro_projeto(self.user, self.projeto)
        self.assertTrue(
            MembroProjeto.objects.filter(user=self.user, projeto=self.projeto).exists()
        )

        adicionar_membro_programa(self.user, self.programa)
        self.assertTrue(
            MembroPrograma.objects.filter(
                user=self.user, programa=self.programa
            ).exists()
        )
        self.assertFalse(
            MembroProjeto.objects.filter(user=self.user, projeto=self.projeto).exists()
        )
        self.assertEqual(get_nivel_acesso(self.user, self.projeto), "membro_programa")

    def test_rebaixamento_sem_confirmacao_levanta_erro(self):
        adicionar_membro_programa(self.user, self.programa)
        with self.assertRaises(ConflitoDeAcessoError):
            adicionar_membro_projeto(self.user, self.projeto, forcar_rebaixamento=False)

    def test_rebaixamento_com_confirmacao_troca_registro(self):
        adicionar_membro_programa(self.user, self.programa)
        adicionar_membro_projeto(self.user, self.projeto, forcar_rebaixamento=True)

        self.assertFalse(
            MembroPrograma.objects.filter(
                user=self.user, programa=self.programa
            ).exists()
        )
        self.assertTrue(
            MembroProjeto.objects.filter(user=self.user, projeto=self.projeto).exists()
        )
        self.assertEqual(get_nivel_acesso(self.user, self.projeto), "membro_projeto")


class PodeAcessarProjetoTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = PodeAcessarProjeto()
        self.cliente = Cliente.objects.create(
            nome="Cliente Teste",
            cnpj="00000000000000",
            nome_contato="Contato",
            email_contato="c@c.com",
            fone_contato="00000",
            numero_contrato="123",
            data_termino_contrato="2030-01-01",
        )
        self.programa = Programa.objects.create(
            nome="Programa Teste", cliente=self.cliente
        )
        self.projeto = Projeto.objects.create(
            nome="Projeto Teste", programa=self.programa
        )
        self.user = User.objects.create_user(
            email="u@test.com", password="password123", full_name="User"
        )

    def _make_request(self, method, user):
        req_func = getattr(self.factory, method.lower())
        request = req_func("/")
        request.user = user
        return request

    def test_sem_acesso_bloqueia_tudo(self):
        request = self._make_request("GET", self.user)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.projeto)
        )

    def test_membro_projeto_edita_mas_nao_deleta(self):
        adicionar_membro_projeto(self.user, self.projeto)

        req_get = self._make_request("GET", self.user)
        self.assertTrue(
            self.permission.has_object_permission(req_get, None, self.projeto)
        )

        req_patch = self._make_request("PATCH", self.user)
        self.assertTrue(
            self.permission.has_object_permission(req_patch, None, self.projeto)
        )

        req_delete = self._make_request("DELETE", self.user)
        self.assertFalse(
            self.permission.has_object_permission(req_delete, None, self.projeto)
        )

    def test_membro_programa_tem_crud_completo_no_projeto(self):
        adicionar_membro_programa(self.user, self.programa)

        req_delete = self._make_request("DELETE", self.user)
        self.assertTrue(
            self.permission.has_object_permission(req_delete, None, self.projeto)
        )

    def test_admin_cliente_tem_acesso_total(self):
        MembroCliente.objects.create(user=self.user, cliente=self.cliente)

        req_delete = self._make_request("DELETE", self.user)
        self.assertTrue(
            self.permission.has_object_permission(req_delete, None, self.projeto)
        )

    def test_admin_gerelat_tem_acesso_total(self):
        MembroGeRelat.objects.create(user=self.user)

        req_delete = self._make_request("DELETE", self.user)
        self.assertTrue(
            self.permission.has_object_permission(req_delete, None, self.projeto)
        )


class ResolverCamposDefinicaoEscopoTest(TestCase):
    def setUp(self):
        # Client 1 (Brisa) -> Program 1 (TIC55) -> Project 1 (FURG1), Project 2 (FURG2)
        # Program 2 (TIC15) under Client 1
        self.cli1 = Cliente.objects.create(
            nome="Brisa",
            cnpj="11111111111111",
            nome_contato="C1",
            email_contato="c1@c.com",
            fone_contato="1111",
            numero_contrato="101",
            data_termino_contrato="2030-01-01",
        )
        self.prog1 = Programa.objects.create(nome="TIC55", cliente=self.cli1)
        self.proj1 = Projeto.objects.create(nome="FURG1", programa=self.prog1)
        self.proj2 = Projeto.objects.create(nome="FURG2", programa=self.prog1)
        self.prog2 = Programa.objects.create(nome="TIC15", cliente=self.cli1)

        # Client 2 (UEA) -> Program 3 -> Project 3
        self.cli2 = Cliente.objects.create(
            nome="UEA",
            cnpj="22222222222222",
            nome_contato="C2",
            email_contato="c2@c.com",
            fone_contato="2222",
            numero_contrato="102",
            data_termino_contrato="2030-01-01",
        )
        self.prog3 = Programa.objects.create(nome="UEAProg", cliente=self.cli2)
        self.proj3 = Projeto.objects.create(nome="UEAProj", programa=self.prog3)

        # CampoDefinicao records
        self.cd_cli1 = CampoDefinicao.objects.create(
            cliente=self.cli1,
            nivel_aplicacao=NivelAplicacao.CLIENTE,
            referencia="ref_cli1",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        self.cd_prog1 = CampoDefinicao.objects.create(
            programa=self.prog1,
            nivel_aplicacao=NivelAplicacao.PROGRAMA,
            referencia="ref_prog1",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        self.cd_proj1 = CampoDefinicao.objects.create(
            projeto=self.proj1,
            nivel_aplicacao=NivelAplicacao.PROJETO,
            referencia="ref_proj1",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        self.cd_proj2 = CampoDefinicao.objects.create(
            projeto=self.proj2,
            nivel_aplicacao=NivelAplicacao.PROJETO,
            referencia="ref_proj2",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        self.cd_prog2 = CampoDefinicao.objects.create(
            programa=self.prog2,
            nivel_aplicacao=NivelAplicacao.PROGRAMA,
            referencia="ref_prog2",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        self.cd_cli2 = CampoDefinicao.objects.create(
            cliente=self.cli2,
            nivel_aplicacao=NivelAplicacao.CLIENTE,
            referencia="ref_cli2",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )

    def test_escopo_projeto(self):
        # Project 1 scope -> should see client 1, program 1, project 1
        res = list(resolver_campos_definicao_escopo(projeto=self.proj1))
        self.assertIn(self.cd_cli1, res)
        self.assertIn(self.cd_prog1, res)
        self.assertIn(self.cd_proj1, res)
        self.assertNotIn(self.cd_proj2, res)
        self.assertNotIn(self.cd_prog2, res)
        self.assertNotIn(self.cd_cli2, res)

    def test_escopo_programa(self):
        # Program 1 scope -> should see client 1 (ancestor) and program 1 (itself), but not child projects
        res = list(resolver_campos_definicao_escopo(programa=self.prog1))
        self.assertIn(self.cd_cli1, res)
        self.assertIn(self.cd_prog1, res)
        self.assertNotIn(self.cd_proj1, res)
        self.assertNotIn(self.cd_proj2, res)
        self.assertNotIn(self.cd_prog2, res)
        self.assertNotIn(self.cd_cli2, res)

    def test_escopo_cliente(self):
        # Client 1 scope -> should see only custom variables of Client 1 (same scope)
        res = list(resolver_campos_definicao_escopo(cliente=self.cli1))
        self.assertIn(self.cd_cli1, res)
        self.assertNotIn(self.cd_prog1, res)
        self.assertNotIn(self.cd_prog2, res)
        self.assertNotIn(self.cd_proj1, res)
        self.assertNotIn(self.cd_proj2, res)
        self.assertNotIn(self.cd_cli2, res)

    def test_build_variables_context_prefixos_ancestrais(self):
        from apps.gerelat.document_engine.variables import build_variables_context
        from apps.gerelat.models import CampoValor

        # Create CampoValor entries with same reference 'atabela' at Client 1, Program 1, and Project 1
        cv_cli = CampoValor.objects.create(
            definicao=self.cd_cli1, cliente=self.cli1, valor="Val Client"
        )
        cv_prog = CampoValor.objects.create(
            definicao=self.cd_prog1, programa=self.prog1, valor="Val Program"
        )
        cv_proj = CampoValor.objects.create(
            definicao=self.cd_proj1, projeto=self.proj1, valor="Val Project"
        )

        ctx = build_variables_context(projeto_id=self.proj1.id)
        # Verify scope prefixes avoid conflicts
        self.assertEqual(ctx["cliente.ref_cli1"], "Val Client")
        self.assertEqual(ctx["programa.ref_prog1"], "Val Program")
        self.assertEqual(ctx["projeto.ref_proj1"], "Val Project")

    def test_bloquear_definicao_evento(self):
        from django.core.exceptions import ValidationError

        cd = CampoDefinicao(
            projeto=self.proj1,
            nivel_aplicacao=NivelAplicacao.EVENTO,
            referencia="ref_invalida",
            descricao="d",
            tipo=CampoTipo.TEXT,
        )
        with self.assertRaises(ValidationError):
            cd.full_clean()


class EventosRelatorioTest(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nome="Cliente E",
            cnpj="33333333333333",
            nome_contato="C3",
            email_contato="c3@c.com",
            fone_contato="3333",
            numero_contrato="103",
            data_termino_contrato="2030-01-01",
        )
        self.prog = Programa.objects.create(nome="Prog E", cliente=self.cli)
        self.proj1 = Projeto.objects.create(nome="Proj 1", programa=self.prog)
        self.proj2 = Projeto.objects.create(nome="Proj 2", programa=self.prog)

        self.ce_proj1 = ClasseEvento.objects.create(
            projeto=self.proj1, nome_classe="Reunião Proj 1"
        )
        self.ce_prog = ClasseEvento.objects.create(
            programa=self.prog, nome_classe="Reunião Prog"
        )

        self.template_proj1 = Template.objects.create(
            projeto=self.proj1,
            nivel=NivelTemplate.PROJETO,
            nome="Template Proj 1",
            modelo_json={"type": "doc", "content": []},
        )
        TemplateClasseEvento.objects.create(
            template=self.template_proj1, classe_evento=self.ce_proj1
        )

        self.evento_valido = Evento.objects.create(
            projeto=self.proj1,
            classe_evento=self.ce_proj1,
            nome="Evento Valido",
            data="2026-08-10",
        )
        self.evento_proj2 = Evento.objects.create(
            projeto=self.proj2,
            classe_evento=self.ce_proj1,
            nome="Evento Proj Outro",
            data="2026-08-10",
        )

    def test_eventos_disponiveis_para_relatorio(self):
        evs = list(eventos_disponiveis_para_relatorio(self.template_proj1))
        self.assertIn(self.evento_valido, evs)
        self.assertNotIn(self.evento_proj2, evs)

    def test_template_sem_classes_vinculadas_aceita_qualquer_evento_do_escopo(self):
        template_sem_classes = Template.objects.create(
            projeto=self.proj1,
            nivel=NivelTemplate.PROJETO,
            nome="Template Sem Classes",
            modelo_json={"type": "doc", "content": []},
        )
        evs = list(eventos_disponiveis_para_relatorio(template_sem_classes))
        self.assertIn(self.evento_valido, evs)
        self.assertNotIn(self.evento_proj2, evs)

    def test_validar_classe_evento_mesmo_escopo(self):
        # ce_prog is scope (programa=self.prog), template_proj1 is scope (projeto=self.proj1)
        with self.assertRaises(ValidationError):
            validar_classe_evento_mesmo_escopo(self.template_proj1, self.ce_prog)

        serializer = TemplateClasseEventoSerializer(
            data={"template": self.template_proj1.id, "classe_evento": self.ce_prog.id}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)


class RelatorioGenerateTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_superuser(
            email="admin@test.com", password="password123", full_name="Admin"
        )
        self.client_api.force_authenticate(user=self.user)

        self.cli = Cliente.objects.create(
            nome="Cliente R",
            cnpj="44444444444444",
            nome_contato="C4",
            email_contato="c4@c.com",
            fone_contato="4444",
            numero_contrato="104",
            data_termino_contrato="2030-01-01",
        )
        self.prog = Programa.objects.create(nome="Prog R", cliente=self.cli)
        self.proj = Projeto.objects.create(nome="Proj R", programa=self.prog)

        self.ce = ClasseEvento.objects.create(projeto=self.proj, nome_classe="Classe R")
        self.template = Template.objects.create(
            projeto=self.proj,
            nivel=NivelTemplate.PROJETO,
            nome="Template R",
            modelo_json={"type": "doc", "content": []},
        )
        TemplateClasseEvento.objects.create(
            template=self.template, classe_evento=self.ce
        )
        # Not linked via TemplateClasseEvento, or linked to another class

        self.ce_outra = ClasseEvento.objects.create(
            projeto=self.proj, nome_classe="Classe Outra"
        )
        self.evento_incompativel = Evento.objects.create(
            projeto=self.proj,
            classe_evento=self.ce_outra,
            nome="Evento Incompativel",
            data="2026-08-10",
        )

    def test_relatorio_create_com_evento_invalido_rejeita(self):
        payload = {
            "template": self.template.id,
            "projeto": self.proj.id,
            "evento": self.evento_incompativel.id,
        }
        response = self.client_api.post("/relatorios/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_relatorio_create_sem_projeto_e_sem_evento_rejeita(self):
        template_programa = Template.objects.create(
            programa=self.prog,
            nivel=NivelTemplate.PROGRAMA,
            nome="Template Prog",
            modelo_json={"type": "doc", "content": []},
        )
        payload = {
            "template": template_programa.id,
        }
        response = self.client_api.post("/relatorios/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("projeto", response.json())

    def test_relatorio_queryset_membro_projeto_enxerga_relatorio_sem_evento(self):
        user_membro = User.objects.create_user(
            email="membro_proj@test.com", password="password123", full_name="Membro"
        )
        MembroProjeto.objects.create(user=user_membro, projeto=self.proj)

        rel = Relatorio.objects.create(
            projeto=self.proj,
            template=self.template,
            nome="Relatorio Direto do Projeto",
            status="SUCCESS",
            documento_json={"type": "doc", "content": []},
        )

        client_membro = APIClient()
        client_membro.force_authenticate(user=user_membro)
        response = client_membro.get("/relatorios/")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(rel.id, ids)

    def test_template_queryset_membro_projeto_enxerga_template_do_programa(self):
        template_programa = Template.objects.create(
            programa=self.prog,
            nivel=NivelTemplate.PROGRAMA,
            nome="Template Herdado do Programa",
            modelo_json={"type": "doc", "content": []},
        )
        user_membro = User.objects.create_user(
            email="membro_p2@test.com", password="password123", full_name="Membro 2"
        )
        MembroProjeto.objects.create(user=user_membro, projeto=self.proj)

        client_membro = APIClient()
        client_membro.force_authenticate(user=user_membro)
        response = client_membro.get("/templates/")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(template_programa.id, ids)


class AssetLogomarcaTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_superuser(
            email="admin@test.com", password="password123", full_name="Admin"
        )
        self.client_api.force_authenticate(user=self.user)
        self.cliente = Cliente.objects.create(
            nome="Cliente Logo Test",
            cnpj="11111111111111",
            nome_contato="Contato",
            email_contato="c@c.com",
            fone_contato="00000",
            numero_contrato="123",
            data_termino_contrato="2030-01-01",
        )
        self.programa = Programa.objects.create(
            nome="Programa Logo Test", cliente=self.cliente
        )

    def test_asset_creation_returns_arquivo_url(self):
        res = self.client_api.post(
            "/assets/",
            {
                "caminho_arquivo": "assets/test-logo.png",
                "cliente": self.cliente.id,
                "descricao": "Logo test",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("arquivo", data)
        self.assertTrue("test-logo.png" in data["arquivo"])

    def test_sincronizar_logomarca_rescoping_and_usage(self):
        asset = Asset.objects.create(
            arquivo="assets/test-programa-logo.png", cliente=self.cliente
        )

        self.programa.logomarca = asset
        self.programa.save()

        asset.refresh_from_db()
        self.assertEqual(asset.programa, self.programa)
        self.assertIsNone(asset.cliente)

        uso = AssetUso.objects.filter(
            asset=asset, tipo_uso=AssetUso.TIPO_USO_LOGOMARCA_PROGRAMA
        ).first()
        self.assertIsNotNone(uso)
        self.assertEqual(uso.programa, self.programa)

    def test_troca_logomarca_cliente_exclui_asset_anterior(self):
        asset1 = Asset.objects.create(
            arquivo="assets/logo-antiga.png", cliente=self.cliente
        )
        self.cliente.logomarca = asset1
        self.cliente.save()

        self.assertTrue(Asset.objects.filter(id=asset1.id).exists())
        self.assertTrue(
            AssetUso.objects.filter(
                asset=asset1,
                cliente=self.cliente,
                tipo_uso=AssetUso.TIPO_USO_LOGOMARCA_CLIENTE,
            ).exists()
        )

        # Troca para um novo asset
        asset2 = Asset.objects.create(
            arquivo="assets/logo-nova.png", cliente=self.cliente
        )
        self.cliente.logomarca = asset2
        self.cliente.save()

        # O asset1 anterior deve ter sido excluído do banco
        self.assertFalse(Asset.objects.filter(id=asset1.id).exists())
        self.assertTrue(Asset.objects.filter(id=asset2.id).exists())
        self.assertEqual(self.cliente.logomarca, asset2)


class AgendamentoRelatorioConcorrenciaTest(TransactionTestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome="Cliente Agendamento Concorrencia",
            data_termino_contrato="2026-12-31",
        )
        self.template = Template.objects.create(
            nome="Template Agendamento Concorrencia",
            nivel=NivelAplicacao.CLIENTE,
            cliente=self.cliente,
            modelo_json={},
        )

    def test_concorrencia_execucao_simultanea_dispara_apenas_uma_vez(self):
        """Duas chamadas concorrentes de executar_agendamento_relatorio para o
        mesmo agendamento devem resultar em apenas um generate_relatorio.delay,
        graças ao select_for_update(skip_locked=True).
        """
        import threading

        from django.db import connection

        from apps.gerelat.tasks import executar_agendamento_relatorio

        agendamento = AgendamentoRelatorio.objects.create(
            nome="Relatorio Concorrencia",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(10, 0),
        )

        patcher = patch("apps.gerelat.tasks.generate_relatorio.delay")
        mock_delay = patcher.start()
        mock_delay.return_value.id = "task-uuid-concurrent"

        barrier = threading.Barrier(2, timeout=5)
        errors = []

        def _run():
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
            try:
                executar_agendamento_relatorio(agendamento.id)
            except Exception as exc:  # pragma: no cover - diagnostico
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=_run) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        patcher.stop()

        self.assertEqual(errors, [])
        # Apenas uma das duas chamadas concorrentes deveria efetivamente
        # disparar generate_relatorio.delay (a outra encontra o registro
        # bloqueado e sai via skip_locked, ou entra na trava de 10s).
        self.assertEqual(mock_delay.call_count, 1)


class DashboardResumoTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.admin = User.objects.create_superuser(
            email="admin_dash@test.com",
            password="password123",
            full_name="Admin Dash",
        )
        self.cli1 = Cliente.objects.create(
            nome="Cliente Dash 1",
            cnpj="11111111111111",
            data_termino_contrato="2030-01-01",
        )
        self.prog1 = Programa.objects.create(nome="Prog Dash 1", cliente=self.cli1)
        self.proj1 = Projeto.objects.create(nome="Proj Dash 1", programa=self.prog1)
        self.ce1 = ClasseEvento.objects.create(
            projeto=self.proj1, nome_classe="Classe 1"
        )
        self.evento1 = Evento.objects.create(
            projeto=self.proj1,
            classe_evento=self.ce1,
            nome="Evento Dash 1",
            data="2026-09-10",
        )
        self.template1 = Template.objects.create(
            projeto=self.proj1,
            nivel=NivelTemplate.PROJETO,
            nome="Template Dash 1",
            modelo_json={"type": "doc", "content": []},
        )
        self.relatorio1 = Relatorio.objects.create(
            projeto=self.proj1,
            template=self.template1,
            nome="Relatorio Dash 1",
            status="SUCCESS",
            documento_json={"type": "doc", "content": []},
        )

        # Segundo cliente
        self.cli2 = Cliente.objects.create(
            nome="Cliente Dash 2",
            cnpj="22222222222222",
            data_termino_contrato="2030-01-01",
        )
        self.prog2 = Programa.objects.create(nome="Prog Dash 2", cliente=self.cli2)
        self.proj2 = Projeto.objects.create(nome="Proj Dash 2", programa=self.prog2)

    def test_admin_resumo_global_e_filtrado(self):
        self.client_api.force_authenticate(user=self.admin)

        # Global
        res_global = self.client_api.get("/dashboard/resumo/")
        self.assertEqual(res_global.status_code, 200)
        data_global = res_global.json()
        self.assertEqual(data_global["programas"], 2)
        self.assertEqual(data_global["projetos"], 2)
        self.assertEqual(data_global["eventos"], 1)
        self.assertEqual(data_global["templates"], 1)
        self.assertEqual(data_global["relatorios"], 1)

        # Filtrado por cliente 1
        res_cli1 = self.client_api.get(f"/dashboard/resumo/?cliente_id={self.cli1.id}")
        self.assertEqual(res_cli1.status_code, 200)
        data_cli1 = res_cli1.json()
        self.assertEqual(data_cli1["programas"], 1)
        self.assertEqual(data_cli1["projetos"], 1)
        self.assertEqual(data_cli1["eventos"], 1)
        self.assertEqual(data_cli1["templates"], 1)
        self.assertEqual(data_cli1["relatorios"], 1)

        # Filtrado por cliente 2
        res_cli2 = self.client_api.get(f"/dashboard/resumo/?cliente_id={self.cli2.id}")
        self.assertEqual(res_cli2.status_code, 200)
        data_cli2 = res_cli2.json()
        self.assertEqual(data_cli2["programas"], 1)
        self.assertEqual(data_cli2["projetos"], 1)
        self.assertEqual(data_cli2["eventos"], 0)
        self.assertEqual(data_cli2["templates"], 0)
        self.assertEqual(data_cli2["relatorios"], 0)

    def test_membro_projeto_resumo_escopado(self):
        user_membro = User.objects.create_user(
            email="membro_dash@test.com",
            password="password123",
            full_name="Membro Dash",
        )
        MembroProjeto.objects.create(user=user_membro, projeto=self.proj1)

        client_membro = APIClient()
        client_membro.force_authenticate(user=user_membro)

        res = client_membro.get("/dashboard/resumo/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["programas"], 1)  # Herdado via projeto
        self.assertEqual(data["projetos"], 1)
        self.assertEqual(data["eventos"], 1)
        self.assertEqual(data["templates"], 1)
        self.assertEqual(data["relatorios"], 1)


class ClienteSerializerTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.cliente = Cliente.objects.create(
            nome="Cliente Secret",
            cnpj="99999999999999",
            nome_contato="CSecret",
            email_contato="secret@c.com",
            fone_contato="9999",
            numero_contrato="CTR-999",
            data_termino_contrato="2028-12-31",
        )
        self.prog = Programa.objects.create(nome="Prog S", cliente=self.cliente)
        self.proj = Projeto.objects.create(nome="Proj S", programa=self.prog)

        self.user_platform_admin = User.objects.create(email="padmin@test.com")
        MembroGeRelat.objects.create(user=self.user_platform_admin)

        self.user_client_admin = User.objects.create(email="cadmin@test.com")
        MembroCliente.objects.create(user=self.user_client_admin, cliente=self.cliente)

        self.user_membro_prog = User.objects.create(email="mprog@test.com")
        MembroPrograma.objects.create(user=self.user_membro_prog, programa=self.prog)

    def test_admin_gerelat_e_admin_cliente_vêem_campos_contrato(self):
        # Platform Admin
        req_padmin = self.factory.get("/clientes/")
        req_padmin.user = self.user_platform_admin
        data_padmin = ClienteSerializer(
            self.cliente, context={"request": req_padmin}
        ).data
        self.assertIn("numero_contrato", data_padmin)
        self.assertIn("data_termino_contrato", data_padmin)
        self.assertEqual(data_padmin["numero_contrato"], "CTR-999")

        # Client Admin
        req_cadmin = self.factory.get("/clientes/")
        req_cadmin.user = self.user_client_admin
        data_cadmin = ClienteSerializer(
            self.cliente, context={"request": req_cadmin}
        ).data
        self.assertIn("numero_contrato", data_cadmin)
        self.assertIn("data_termino_contrato", data_cadmin)

    def test_membro_programa_nao_ve_campos_contrato(self):
        req_mprog = self.factory.get("/clientes/")
        req_mprog.user = self.user_membro_prog
        data_mprog = ClienteSerializer(
            self.cliente, context={"request": req_mprog}
        ).data
        self.assertNotIn("numero_contrato", data_mprog)
        self.assertNotIn("data_termino_contrato", data_mprog)

    def test_client_admin_nao_pode_editar_campos_contrato(self):
        req = self.factory.put("/clientes/1/")
        req.user = self.user_client_admin
        data = {
            "nome": "Cliente Alterado",
            "cnpj": "99999999999999",
            "nome_contato": "CSecret",
            "email_contato": "secret@c.com",
            "fone_contato": "9999",
            "numero_contrato": "NOVO-CTR",
            "data_termino_contrato": "2028-12-31",
        }
        serializer = ClienteSerializer(
            self.cliente, data=data, context={"request": req}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("numero_contrato", serializer.errors)

    def test_platform_admin_pode_editar_campos_contrato(self):
        req = self.factory.put("/clientes/1/")
        req.user = self.user_platform_admin
        data = {
            "nome": "Cliente Alterado",
            "cnpj": "99999999999999",
            "nome_contato": "CSecret",
            "email_contato": "secret@c.com",
            "fone_contato": "9999",
            "numero_contrato": "NOVO-CTR",
            "data_termino_contrato": "2029-01-01",
        }
        serializer = ClienteSerializer(
            self.cliente, data=data, context={"request": req}
        )
        self.assertTrue(serializer.is_valid())


class AssetDeletionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_admin = User.objects.create_user(
            email="admin_g@test.com", password="pass", full_name="Admin G"
        )
        MembroGeRelat.objects.create(user=self.user_admin)

        self.cliente = Cliente.objects.create(
            nome="Cliente A",
            cnpj="11111111111111",
            nome_contato="C1",
            email_contato="c1@test.com",
            fone_contato="1111",
            numero_contrato="CTR-1",
            data_termino_contrato="2027-12-31",
        )
        self.user_cliente_admin = User.objects.create_user(
            email="client_admin@test.com", password="pass", full_name="Client Admin"
        )
        MembroCliente.objects.create(user=self.user_cliente_admin, cliente=self.cliente)

        self.programa = Programa.objects.create(
            cliente=self.cliente,
            nome="Programa P1",
        )
        self.user_membro_prog = User.objects.create_user(
            email="prog_member@test.com", password="pass", full_name="Prog Member"
        )
        MembroPrograma.objects.create(
            user=self.user_membro_prog, programa=self.programa
        )

        self.projeto = Projeto.objects.create(
            programa=self.programa,
            nome="Projeto PJ1",
        )
        self.user_membro_proj = User.objects.create_user(
            email="proj_member@test.com", password="pass", full_name="Proj Member"
        )
        MembroProjeto.objects.create(user=self.user_membro_proj, projeto=self.projeto)

    def test_asset_em_uso_nao_pode_ser_excluido(self):
        asset = Asset.objects.create(
            cliente=self.cliente, descricao="Logomarca Cliente"
        )
        AssetUso.objects.create(
            asset=asset,
            tipo_uso=AssetUso.TIPO_USO_LOGOMARCA_CLIENTE,
            cliente=self.cliente,
        )

        self.client.force_authenticate(user=self.user_admin)
        res = self.client.delete(f"/assets/{asset.id}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("está em uso", res.data["detail"])

    def test_asset_sem_uso_excluido_com_sucesso(self):
        asset = Asset.objects.create(cliente=self.cliente, descricao="Sem Uso")
        self.client.force_authenticate(user=self.user_admin)
        res = self.client.delete(f"/assets/{asset.id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Asset.objects.filter(id=asset.id).exists())

    def test_permissao_exclusao_por_escopo(self):
        asset_cliente = Asset.objects.create(cliente=self.cliente)
        asset_programa = Asset.objects.create(programa=self.programa)
        asset_projeto = Asset.objects.create(projeto=self.projeto)

        # Membro de projeto tenta excluir asset do cliente -> 403
        self.client.force_authenticate(user=self.user_membro_proj)
        res = self.client.delete(f"/assets/{asset_cliente.id}/")
        self.assertEqual(res.status_code, 403)

        # Membro de projeto tenta excluir asset do programa -> 403
        res = self.client.delete(f"/assets/{asset_programa.id}/")
        self.assertEqual(res.status_code, 403)

        # Membro de projeto exclui asset do próprio projeto -> 204
        res = self.client.delete(f"/assets/{asset_projeto.id}/")
        self.assertEqual(res.status_code, 204)

        # Membro do programa exclui asset do programa -> 204
        self.client.force_authenticate(user=self.user_membro_prog)
        res = self.client.delete(f"/assets/{asset_programa.id}/")
        self.assertEqual(res.status_code, 204)

    def test_campo_valor_imagem_cria_asset_uso_e_impede_exclusao(self):
        asset = Asset.objects.create(cliente=self.cliente, descricao="Imagem Variavel")
        definicao = CampoDefinicao.objects.create(
            cliente=self.cliente,
            nivel_aplicacao=NivelAplicacao.CLIENTE,
            referencia="foto_capa",
            tipo=CampoTipo.IMAGE,
        )
        campo_valor = CampoValor.objects.create(
            definicao=definicao,
            cliente=self.cliente,
            valor={"asset_id": asset.id, "caption": "Capa"},
        )

        self.assertTrue(
            AssetUso.objects.filter(asset=asset, campo_valor=campo_valor).exists()
        )

        # Tentar excluir o asset deve falhar com 400
        self.client.force_authenticate(user=self.user_admin)
        res = self.client.delete(f"/assets/{asset.id}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("está em uso", res.data["detail"])


class AgendamentoRelatorioTest(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome="Cliente Agendamento",
            data_termino_contrato="2026-12-31",
        )
        self.template = Template.objects.create(
            nome="Template Agendamento",
            nivel=NivelAplicacao.CLIENTE,
            cliente=self.cliente,
            modelo_json={},
        )

    def _criar_agendamento(self, **kwargs):
        """Cria um AgendamentoRelatorio e sincroniza a PeriodicTask, exatamente
        como a API (AgendamentoRelatorioViewSet.perform_create) faz. save()
        por si só não sincroniza mais o Celery Beat automaticamente.
        """
        agendamento = AgendamentoRelatorio.objects.create(**kwargs)
        sincronizar_periodic_task(agendamento)
        agendamento.refresh_from_db()
        return agendamento

    def _atualizar_agendamento(self, agendamento, **kwargs):
        """Atualiza campos e sincroniza a PeriodicTask, como a API
        (AgendamentoRelatorioViewSet.perform_update) faz.
        """
        for campo, valor in kwargs.items():
            setattr(agendamento, campo, valor)
        agendamento.save()
        sincronizar_periodic_task(agendamento)
        agendamento.refresh_from_db()
        return agendamento

    def test_agendamento_pontual_cria_clocked_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        exec_time = timezone.now() + timedelta(days=1)
        agendamento = self._criar_agendamento(
            nome="Relatorio Pontual",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=exec_time,
        )
        self.assertTrue(agendamento.ativo)
        self.assertIsNotNone(agendamento.periodic_task)
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task.id)
        self.assertTrue(pt.one_off)
        self.assertIsNotNone(pt.clocked)
        self.assertEqual(pt.task, "apps.gerelat.tasks.executar_agendamento_relatorio")

    def test_agendamento_recorrente_cria_crontab_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Recorrente",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(19, 30),
        )
        self.assertTrue(agendamento.ativo)
        self.assertIsNotNone(agendamento.periodic_task)
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task.id)
        self.assertFalse(pt.one_off)
        self.assertIsNotNone(pt.crontab)
        self.assertEqual(pt.crontab.hour, "19")
        self.assertEqual(pt.crontab.minute, "30")

    def test_executar_agendamento_relatorio_task(self):
        from apps.gerelat.tasks import executar_agendamento_relatorio

        exec_time = timezone.now() - timedelta(minutes=5)
        agendamento = self._criar_agendamento(
            nome="Relatorio Executar Task",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=exec_time,
        )

        with patch("apps.gerelat.tasks.generate_relatorio.delay") as mock_delay:
            mock_delay.return_value.id = "task-uuid-123"
            executar_agendamento_relatorio(agendamento.id)
            mock_delay.assert_called_once()

        agendamento.refresh_from_db()
        self.assertFalse(agendamento.ativo)
        self.assertIsNotNone(agendamento.ultima_execucao)

    def test_recorrencia_mensal_dia_31_usa_clocked_schedule(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Mensal 31",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_MENSAL,
            dia_mes=31,
            horario_execucao=time(10, 0),
        )
        self.assertIsNotNone(agendamento.proxima_execucao)
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task.id)
        # Deve usar ClockedSchedule para dia 31 para garantir compatibilidade com meses de < 31 dias
        self.assertIsNotNone(pt.clocked)
        self.assertIsNone(pt.crontab)
        self.assertEqual(pt.clocked.clocked_time, agendamento.proxima_execucao)
        self.assertTrue(pt.one_off)
        self.assertTrue(pt.enabled)

    def test_executar_agendamento_recorrencia_mensal_dia_31_reagenda_proximo_mes(self):
        from django_celery_beat.models import PeriodicTask

        from apps.gerelat.tasks import executar_agendamento_relatorio

        agendamento = self._criar_agendamento(
            nome="Relatorio Mensal 31 Continuous",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_MENSAL,
            dia_mes=31,
            horario_execucao=time(10, 0),
        )
        first_proxima = agendamento.proxima_execucao
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task.id)
        self.assertTrue(pt.enabled)

        with patch("apps.gerelat.tasks.generate_relatorio.delay") as mock_delay:
            mock_delay.return_value.id = "task-uuid-mensal"
            executar_agendamento_relatorio(agendamento.id)
            mock_delay.assert_called_once()

        agendamento.refresh_from_db()
        self.assertTrue(agendamento.ativo)
        self.assertIsNotNone(agendamento.ultima_execucao)
        self.assertGreater(agendamento.proxima_execucao, first_proxima)

        pt.refresh_from_db()
        self.assertTrue(pt.enabled)
        self.assertTrue(pt.one_off)
        self.assertEqual(pt.clocked.clocked_time, agendamento.proxima_execucao)

    def test_atualizacao_agendamento_recalcula_proxima_execucao(self):
        agendamento = self._criar_agendamento(
            nome="Relatorio Recorrente Para Atualizar",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(10, 0),
        )
        proxima_orig = agendamento.proxima_execucao
        self.assertIsNotNone(proxima_orig)

        # Atualizar o horário de execução
        agendamento = self._atualizar_agendamento(
            agendamento, horario_execucao=time(15, 30)
        )

        self.assertNotEqual(agendamento.proxima_execucao, proxima_orig)
        tz = timezone.get_current_timezone()
        dt_local = agendamento.proxima_execucao.astimezone(tz)
        self.assertEqual(dt_local.hour, 15)
        self.assertEqual(dt_local.minute, 30)

    def test_excluir_agendamento_remove_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Para Deletar",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=timezone.now() + timedelta(hours=1),
        )
        pt_id = agendamento.periodic_task.id
        self.assertTrue(PeriodicTask.objects.filter(id=pt_id).exists())

        pt = agendamento.periodic_task
        agendamento_id = agendamento.id
        agendamento.delete()
        remover_periodic_task(agendamento_id, pt)
        self.assertFalse(PeriodicTask.objects.filter(id=pt_id).exists())

    def test_dia_semana_mapeamento_cron_e_python(self):
        # 1=Segunda, 7=Domingo
        self.assertEqual(dia_semana_para_python_weekday(1), 0)  # Segunda -> 0 Python
        self.assertEqual(dia_semana_para_python_weekday(7), 6)  # Domingo -> 6 Python

        self.assertEqual(dia_semana_para_cron_weekday(1), "1")  # Segunda -> 1 Cron
        self.assertEqual(dia_semana_para_cron_weekday(7), "0")  # Domingo -> 0 Cron

    def test_agendamento_constraint_escopo_unico(self):
        # Sem nenhum escopo deve falhar na CheckConstraint
        with self.assertRaises(IntegrityError):
            AgendamentoRelatorio.objects.create(
                nome="Sem Escopo",
                template=self.template,
                tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
                data_hora_execucao=timezone.now() + timedelta(days=1),
            )

    def test_agendamento_serializer_validacao_escopo(self):
        programa = Programa.objects.create(nome="Prog Teste", cliente=self.cliente)

        # Ao passar apenas o template (sem escopo explícito), o serializer deriva o escopo do template (cliente)
        data = {
            "nome": "Agendamento com Template",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_PONTUAL,
            "data_hora_execucao": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        serializer = AgendamentoRelatorioSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["cliente"], self.cliente)
        self.assertIsNone(serializer.validated_data.get("programa"))
        self.assertIsNone(serializer.validated_data.get("projeto"))

    def test_agendamento_pontual_passado_nao_pode_ativar(self):
        data = {
            "nome": "Agendamento Passado",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_PONTUAL,
            "data_hora_execucao": (timezone.now() - timedelta(days=1)).isoformat(),
            "ativo": True,
        }
        serializer = AgendamentoRelatorioSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("ativo", serializer.errors)

    def test_serializer_validacao_dia_semana_e_dia_mes_invalidos(self):
        # Recorrência semanal sem dia_semana ou fora de 1..7
        data_sem_dia_semana = {
            "nome": "Semanal sem dia_semana",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_RECORRENTE,
            "recorrencia": AgendamentoRelatorio.RECORRENCIA_SEMANAL,
            "horario_execucao": "08:00:00",
        }
        ser = AgendamentoRelatorioSerializer(data=data_sem_dia_semana)
        self.assertFalse(ser.is_valid())
        self.assertIn("dia_semana", ser.errors)

        data_dia_semana_invalido = {
            **data_sem_dia_semana,
            "dia_semana": 8,
        }
        ser = AgendamentoRelatorioSerializer(data=data_dia_semana_invalido)
        self.assertFalse(ser.is_valid())
        self.assertIn("dia_semana", ser.errors)

        # Recorrência mensal sem dia_mes ou fora de 1..31
        data_sem_dia_mes = {
            "nome": "Mensal sem dia_mes",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_RECORRENTE,
            "recorrencia": AgendamentoRelatorio.RECORRENCIA_MENSAL,
            "horario_execucao": "08:00:00",
        }
        ser = AgendamentoRelatorioSerializer(data=data_sem_dia_mes)
        self.assertFalse(ser.is_valid())
        self.assertIn("dia_mes", ser.errors)

        data_dia_mes_invalido = {
            **data_sem_dia_mes,
            "dia_mes": 32,
        }
        ser = AgendamentoRelatorioSerializer(data=data_dia_mes_invalido)
        self.assertFalse(ser.is_valid())
        self.assertIn("dia_mes", ser.errors)

    def test_recorrencia_mensal_fevereiro_ano_bissexto_e_comum(self):
        tz = timezone.get_current_timezone()
        agendamento = AgendamentoRelatorio(
            nome="Mensal Fev Test",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_MENSAL,
            dia_mes=31,
            horario_execucao=time(8, 0),
        )

        # 31 de Jan de 2027 (ano comum, fev tem 28 dias)
        ref_2027 = timezone.make_aware(datetime(2027, 1, 31, 8, 0, 0), tz)
        proxima = agendamento.calcular_proxima_execucao(a_partir_de=ref_2027)
        dt_local = proxima.astimezone(tz)
        self.assertEqual(dt_local.year, 2027)
        self.assertEqual(dt_local.month, 2)
        self.assertEqual(dt_local.day, 28)

        # 31 de Jan de 2028 (ano bissexto, fev tem 29 dias)
        ref_2028 = timezone.make_aware(datetime(2028, 1, 31, 8, 0, 0), tz)
        proxima_bissexto = agendamento.calcular_proxima_execucao(a_partir_de=ref_2028)
        dt_local_b = proxima_bissexto.astimezone(tz)
        self.assertEqual(dt_local_b.year, 2028)
        self.assertEqual(dt_local_b.month, 2)
        self.assertEqual(dt_local_b.day, 29)

    def test_servico_sincronizar_periodic_task_isolado_do_save(self):
        """Garante que a sincronização pode ser testada/chamada isoladamente
        via services.agendamento_relatorio, sem depender do ciclo de save().
        """
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Servico Isolado",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(11, 0),
        )
        pt_id_original = agendamento.periodic_task_id
        self.assertIsNotNone(pt_id_original)

        # Muda o horário diretamente no objeto em memória (sem passar por
        # save()) e chama o serviço isoladamente para confirmar que ele, por
        # si só, reflete a mudança no PeriodicTask.
        agendamento.horario_execucao = time(14, 45)
        sincronizar_periodic_task(agendamento)

        pt = PeriodicTask.objects.get(id=pt_id_original)
        self.assertEqual(pt.crontab.hour, "14")
        self.assertEqual(pt.crontab.minute, "45")

    def test_servico_remover_periodic_task_limpa_clocked_orfao(self):
        from django_celery_beat.models import ClockedSchedule, PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Servico Remover",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=timezone.now() + timedelta(days=3),
        )
        pt = agendamento.periodic_task
        clocked_id = pt.clocked_id
        self.assertIsNotNone(clocked_id)

        remover_periodic_task(agendamento.id, pt)

        self.assertFalse(PeriodicTask.objects.filter(id=pt.id).exists())
        self.assertFalse(ClockedSchedule.objects.filter(id=clocked_id).exists())

    def test_executar_agendamento_relatorio_duplicado_imediato_ignora(self):
        from apps.gerelat.tasks import executar_agendamento_relatorio

        agendamento = self._criar_agendamento(
            nome="Relatorio Duplicate Check",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(10, 0),
        )

        with patch("apps.gerelat.tasks.generate_relatorio.delay") as mock_delay:
            mock_delay.return_value.id = "task-uuid-1"
            executar_agendamento_relatorio(agendamento.id)
            self.assertEqual(mock_delay.call_count, 1)

            # Segunda chamada imediata (ultima_execucao < 10s atrás)
            executar_agendamento_relatorio(agendamento.id)
            # Não deve ter incrementado mock_delay.call_count
            self.assertEqual(mock_delay.call_count, 1)

    def test_recorrencia_mensal_dia_31_encadeia_multiplos_meses(self):
        """Garante que, apos cada execucao, o PeriodicTask.clocked eh
        atualizado para o proximo ciclo real (31/08 -> 30/09 -> 31/10 -> 30/11 -> 31/12 -> 31/01).
        """
        from django_celery_beat.models import PeriodicTask

        from apps.gerelat.tasks import executar_agendamento_relatorio

        tz = timezone.get_current_timezone()
        data_base = datetime(2026, 8, 1, 10, 0, tzinfo=tz)
        with patch("django.utils.timezone.now", return_value=data_base):
            agendamento = self._criar_agendamento(
                nome="Relatorio Mensal 31 Multi",
                template=self.template,
                cliente=self.cliente,
                tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
                recorrencia=AgendamentoRelatorio.RECORRENCIA_MENSAL,
                dia_mes=31,
                horario_execucao=time(10, 0),
            )

        # (ano, mes) esperado antes de cada execucao -> (ano, mes, dia) esperado apos a execucao
        expected_sequence = [
            (2026, 8, 31),
            (2026, 9, 30),
            (2026, 10, 31),
            (2026, 11, 30),
            (2026, 12, 31),
            (2027, 1, 31),
        ]

        # Garante que a primeira proxima_execucao calculada bate com a sequencia esperada
        primeira = agendamento.proxima_execucao.astimezone(tz)
        self.assertEqual(
            (primeira.year, primeira.month, primeira.day), expected_sequence[0]
        )

        for _, _, _ in expected_sequence[1:]:
            pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
            self.assertIsNotNone(pt.clocked)
            self.assertIsNone(pt.crontab)
            self.assertEqual(pt.clocked.clocked_time, agendamento.proxima_execucao)

            # Simula o Beat disparando exatamente no horario agendado
            execucao_simulada = agendamento.proxima_execucao
            with patch(
                "apps.gerelat.tasks.timezone.now", return_value=execucao_simulada
            ):
                with patch("apps.gerelat.tasks.generate_relatorio.delay") as mock_delay:
                    mock_delay.return_value.id = "task-uuid-mensal-chain"
                    executar_agendamento_relatorio(agendamento.id)
                    mock_delay.assert_called_once()

            agendamento.refresh_from_db()

        # Apos processar todas as execucoes da sequencia, confirma o ultimo ciclo
        ultima = agendamento.proxima_execucao.astimezone(tz)
        self.assertEqual((ultima.year, ultima.month, ultima.day), expected_sequence[-1])
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
        self.assertEqual(pt.clocked.clocked_time, agendamento.proxima_execucao)
        self.assertTrue(pt.enabled)
        self.assertTrue(pt.one_off)

    def test_alternar_tipo_pontual_para_recorrente_e_volta(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Alternancia Tipo",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=timezone.now() + timedelta(days=1),
        )
        pt_id = agendamento.periodic_task_id
        pt = PeriodicTask.objects.get(id=pt_id)
        self.assertIsNotNone(pt.clocked)
        self.assertIsNone(pt.crontab)
        self.assertTrue(pt.one_off)

        # Pontual -> Recorrente
        agendamento = self._atualizar_agendamento(
            agendamento,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(9, 0),
        )

        pt.refresh_from_db()
        self.assertIsNone(pt.clocked)
        self.assertIsNotNone(pt.crontab)
        self.assertFalse(pt.one_off)

        # Recorrente -> Pontual novamente
        agendamento = self._atualizar_agendamento(
            agendamento,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=timezone.now() + timedelta(days=2),
        )

        pt.refresh_from_db()
        self.assertIsNotNone(pt.clocked)
        self.assertIsNone(pt.crontab)
        self.assertTrue(pt.one_off)

    def test_alternar_recorrencia_diario_semanal_mensal(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Alternancia Recorrencia",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(9, 0),
        )
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
        self.assertEqual(pt.crontab.day_of_week, "*")
        self.assertEqual(pt.crontab.day_of_month, "*")

        # Diario -> Semanal
        agendamento = self._atualizar_agendamento(
            agendamento,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_SEMANAL,
            dia_semana=3,
        )
        pt.refresh_from_db()
        self.assertEqual(pt.crontab.day_of_week, dia_semana_para_cron_weekday(3))
        self.assertEqual(pt.crontab.day_of_month, "*")

        # Semanal -> Mensal (dia <= 28, usa crontab)
        agendamento = self._atualizar_agendamento(
            agendamento,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_MENSAL,
            dia_mes=15,
        )
        pt.refresh_from_db()
        self.assertIsNotNone(pt.crontab)
        self.assertIsNone(pt.clocked)
        self.assertEqual(pt.crontab.day_of_month, "15")

        # Mensal -> Diario novamente
        agendamento = self._atualizar_agendamento(
            agendamento, recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO
        )
        pt.refresh_from_db()
        self.assertEqual(pt.crontab.day_of_week, "*")
        self.assertEqual(pt.crontab.day_of_month, "*")

    def test_alternar_ativo_inativo_desabilita_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        agendamento = self._criar_agendamento(
            nome="Relatorio Ativo Inativo",
            template=self.template,
            cliente=self.cliente,
            tipo_agendamento=AgendamentoRelatorio.TIPO_RECORRENTE,
            recorrencia=AgendamentoRelatorio.RECORRENCIA_DIARIO,
            horario_execucao=time(9, 0),
        )
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
        self.assertTrue(pt.enabled)
        self.assertIsNotNone(agendamento.proxima_execucao)

        agendamento = self._atualizar_agendamento(agendamento, ativo=False)
        pt.refresh_from_db()
        self.assertFalse(pt.enabled)
        self.assertIsNone(agendamento.proxima_execucao)

        agendamento = self._atualizar_agendamento(agendamento, ativo=True)
        pt.refresh_from_db()
        self.assertTrue(pt.enabled)
        self.assertIsNotNone(agendamento.proxima_execucao)

    def test_troca_template_com_evento_incompativel_limpa_evento(self):
        outro_cliente = Cliente.objects.create(
            nome="Outro Cliente Template Swap",
            data_termino_contrato="2026-12-31",
        )
        outro_template = Template.objects.create(
            nome="Outro Template",
            nivel=NivelAplicacao.CLIENTE,
            cliente=outro_cliente,
            modelo_json={},
        )
        ce_swap = ClasseEvento.objects.create(
            cliente=self.cliente, nome_classe="Classe Swap"
        )
        evento = Evento.objects.create(
            nome="Evento do Cliente Original",
            cliente=self.cliente,
            classe_evento=ce_swap,
            data="2026-08-10",
        )
        agendamento = AgendamentoRelatorio.objects.create(
            nome="Relatorio Template Swap",
            template=self.template,
            cliente=self.cliente,
            evento=evento,
            tipo_agendamento=AgendamentoRelatorio.TIPO_PONTUAL,
            data_hora_execucao=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(agendamento.evento_id, evento.id)

        serializer = AgendamentoRelatorioSerializer(
            agendamento,
            data={"template": outro_template.id},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        atualizado = serializer.save()
        self.assertIsNone(atualizado.evento_id)
        self.assertEqual(atualizado.cliente_id, outro_cliente.id)


class AgendamentoRelatorioAPITest(TestCase):
    """Cobre o caminho real de produção: criação/edição/exclusão via
    AgendamentoRelatorioViewSet, garantindo que perform_create/
    perform_update/perform_destroy sincronizam a PeriodicTask explicitamente
    (sem depender de save()/delete() do model fazerem isso implicitamente).
    """

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_superuser(
            email="admin_agendamento@test.com",
            password="password123",
            full_name="Admin Agendamento",
        )
        self.client_api.force_authenticate(user=self.user)

        self.cliente = Cliente.objects.create(
            nome="Cliente Agendamento API",
            data_termino_contrato="2026-12-31",
        )
        self.template = Template.objects.create(
            nome="Template Agendamento API",
            nivel=NivelAplicacao.CLIENTE,
            cliente=self.cliente,
            modelo_json={},
        )

    def test_criar_agendamento_via_api_sincroniza_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        payload = {
            "nome": "Agendamento via API",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_RECORRENTE,
            "recorrencia": AgendamentoRelatorio.RECORRENCIA_DIARIO,
            "horario_execucao": "08:00:00",
        }
        res = self.client_api.post("/agendamentos-relatorio/", payload, format="json")
        self.assertEqual(res.status_code, 201, res.data)

        agendamento = AgendamentoRelatorio.objects.get(id=res.data["id"])
        self.assertIsNotNone(agendamento.periodic_task_id)
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
        self.assertEqual(pt.crontab.hour, "8")
        self.assertEqual(pt.crontab.minute, "0")

    def test_editar_agendamento_via_api_resincroniza_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        create_payload = {
            "nome": "Agendamento API Editar",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_RECORRENTE,
            "recorrencia": AgendamentoRelatorio.RECORRENCIA_DIARIO,
            "horario_execucao": "08:00:00",
        }
        res = self.client_api.post(
            "/agendamentos-relatorio/", create_payload, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        agendamento_id = res.data["id"]

        res = self.client_api.patch(
            f"/agendamentos-relatorio/{agendamento_id}/",
            {"horario_execucao": "20:15:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)

        agendamento = AgendamentoRelatorio.objects.get(id=agendamento_id)
        pt = PeriodicTask.objects.get(id=agendamento.periodic_task_id)
        self.assertEqual(pt.crontab.hour, "20")
        self.assertEqual(pt.crontab.minute, "15")

    def test_excluir_agendamento_via_api_remove_periodic_task(self):
        from django_celery_beat.models import PeriodicTask

        create_payload = {
            "nome": "Agendamento API Excluir",
            "template": self.template.id,
            "tipo_agendamento": AgendamentoRelatorio.TIPO_PONTUAL,
            "data_hora_execucao": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        res = self.client_api.post(
            "/agendamentos-relatorio/", create_payload, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        agendamento_id = res.data["id"]
        pt_id = AgendamentoRelatorio.objects.get(id=agendamento_id).periodic_task_id
        self.assertTrue(PeriodicTask.objects.filter(id=pt_id).exists())

        res = self.client_api.delete(f"/agendamentos-relatorio/{agendamento_id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            AgendamentoRelatorio.objects.filter(id=agendamento_id).exists()
        )
        self.assertFalse(PeriodicTask.objects.filter(id=pt_id).exists())


class TextoRicoAninhadoTest(TestCase):
    """Resolução recursiva de variáveis dentro do valor de um texto rico
    (document_engine.converters) + propagação de escopo (document_engine.scope)
    + guardas de validação (document_engine.validators)."""

    def _doc(self, *blocos):
        return {"type": "doc", "content": list(blocos)}

    def _par(self, *inline):
        return {"type": "paragraph", "content": list(inline)}

    def _txt(self, texto):
        return {"type": "text", "text": texto}

    def _var_text(self, ref):
        return {"type": "var_text", "attrs": {"ref": ref}}

    # ── converters.replace_placeholders ────────────────────────────

    def test_var_text_dentro_de_valor_richtext_resolve(self):
        from apps.gerelat.document_engine.converters import replace_placeholders

        template = self._doc({"type": "var_richtext", "attrs": {"ref": "texto_padrao"}})
        variables = {
            "texto_padrao": self._doc(
                self._par(
                    self._txt("Parceira: "),
                    self._var_text("nome_parceira"),
                    self._txt("."),
                )
            ),
            "nome_parceira": "FURG",
        }

        resultado = replace_placeholders(template, variables)
        inline = resultado["content"][0]["content"]
        self.assertEqual(
            [n.get("text") for n in inline if n.get("type") == "text"],
            ["Parceira: ", "FURG", "."],
        )
        self.assertFalse(any(n.get("type") == "var_text" for n in inline))

    def test_sistema_dentro_de_valor_richtext_resolve(self):
        from apps.gerelat.document_engine.converters import replace_placeholders

        template = self._doc({"type": "var_richtext", "attrs": {"ref": "texto_padrao"}})
        variables = {
            "texto_padrao": self._doc(
                self._par(
                    self._txt("Evento "),
                    self._var_text("sistema.evento.nome"),
                    self._txt("."),
                )
            ),
            "sistema.evento.nome": "Oficina",
        }

        resultado = replace_placeholders(template, variables)
        textos = [
            n["text"]
            for n in resultado["content"][0]["content"]
            if n.get("type") == "text"
        ]
        self.assertEqual(textos, ["Evento ", "Oficina", "."])

    def test_ciclo_richtext_nao_estoura_pilha(self):
        from apps.gerelat.document_engine.converters import replace_placeholders

        template = self._doc({"type": "var_richtext", "attrs": {"ref": "a"}})
        variables = {
            "a": self._doc({"type": "var_richtext", "attrs": {"ref": "b"}}),
            "b": self._doc({"type": "var_richtext", "attrs": {"ref": "a"}}),
        }

        resultado = replace_placeholders(template, variables)
        texto_plano = str(resultado)
        self.assertIn("ciclo de variáveis", texto_plano)

    def test_var_richtext_sem_valor_mantem_placeholder(self):
        from apps.gerelat.document_engine.converters import replace_placeholders

        template = self._doc({"type": "var_richtext", "attrs": {"ref": "x"}})
        resultado = replace_placeholders(template, {})
        self.assertEqual(resultado["content"][0]["type"], "var_richtext")

    # ── validators.validate_richtext ──────────────────────────────

    def test_validate_richtext_rejeita_richtext_aninhado(self):
        from django.core.exceptions import ValidationError

        from apps.gerelat.document_engine.validators import validate_richtext

        with self.assertRaises(ValidationError):
            validate_richtext(
                self._doc({"type": "var_richtext", "attrs": {"ref": "outro"}})
            )

    def test_validate_richtext_rejeita_custom_text(self):
        from django.core.exceptions import ValidationError

        from apps.gerelat.document_engine.validators import validate_richtext

        with self.assertRaises(ValidationError):
            validate_richtext(
                self._doc(
                    {
                        "type": "custom_text",
                        "attrs": {"label": "bloco"},
                        "content": [self._par(self._txt("x"))],
                    }
                )
            )

    def test_validate_richtext_rejeita_var_sem_ref(self):
        from django.core.exceptions import ValidationError

        from apps.gerelat.document_engine.validators import validate_richtext

        with self.assertRaises(ValidationError):
            validate_richtext(
                self._doc(self._par({"type": "var_text", "attrs": {"ref": ""}}))
            )

    def test_validate_richtext_aceita_var_text_com_ref(self):
        from apps.gerelat.document_engine.validators import validate_richtext

        validate_richtext(
            self._doc(self._par(self._txt("oi "), self._var_text("nome_parceira")))
        )

    # ── scope.scan_required_nivel (propagação transitiva) ─────────

    def test_scan_required_nivel_propaga_por_valor_richtext(self):
        from apps.gerelat.document_engine.scope import scan_required_nivel

        cli = Cliente.objects.create(
            nome="Brisa",
            cnpj="11111111111111",
            nome_contato="C1",
            email_contato="c1@c.com",
            fone_contato="1111",
            numero_contrato="101",
            data_termino_contrato="2030-01-01",
        )
        prog = Programa.objects.create(nome="TIC55", cliente=cli)

        definicao = CampoDefinicao.objects.create(
            programa=prog,
            nivel_aplicacao=NivelAplicacao.PROGRAMA,
            referencia="texto_padrao",
            descricao="d",
            tipo=CampoTipo.RICHTEXT,
        )
        CampoValor.objects.create(
            definicao=definicao,
            programa=prog,
            valor=self._doc(
                self._par(
                    self._txt("Evento "),
                    self._var_text("sistema.evento.nome"),
                )
            ),
        )

        template_json = self._doc(
            {"type": "var_richtext", "attrs": {"ref": "texto_padrao"}}
        )

        # Sem a expansão transitiva, o template só cita "texto_padrao" (programa).
        nivel = scan_required_nivel(template_json, cliente=cli, programa=prog)
        self.assertEqual(nivel, "evento")

    def test_scan_required_nivel_propaga_por_campo_customizado_de_projeto(self):
        """Mesmo cenário relatado em produção: um texto rico de nível PROGRAMA
        (mesmo valor para todo projeto do programa) cujo conteúdo cita uma
        CampoDefinicao customizada — não um campo sistema.* — cujo
        nivel_aplicacao é PROJETO. O nível exigido pelo template tem que
        refletir essa dependência escondida dentro do texto rico, mesmo que
        nenhum projeto tenha sido informado ainda."""
        from apps.gerelat.document_engine.scope import scan_required_nivel

        cli = Cliente.objects.create(
            nome="Brisa",
            cnpj="22222222222222",
            nome_contato="C2",
            email_contato="c2@c.com",
            fone_contato="2222",
            numero_contrato="102",
            data_termino_contrato="2030-01-01",
        )
        prog = Programa.objects.create(nome="TIC56", cliente=cli)

        CampoDefinicao.objects.create(
            programa=prog,
            nivel_aplicacao=NivelAplicacao.PROJETO,
            referencia="nome_escola",
            descricao="Escola atendida pelo projeto",
            tipo=CampoTipo.TEXT,
        )
        cd_texto = CampoDefinicao.objects.create(
            programa=prog,
            nivel_aplicacao=NivelAplicacao.PROGRAMA,
            referencia="texto_padrao",
            descricao="Parágrafo padrão do relatório",
            tipo=CampoTipo.RICHTEXT,
        )
        CampoValor.objects.create(
            definicao=cd_texto,
            programa=prog,
            valor=self._doc(
                self._par(
                    self._txt("Atividade realizada na escola "),
                    self._var_text("nome_escola"),
                    self._txt("."),
                )
            ),
        )

        template_json = self._doc(
            {"type": "var_richtext", "attrs": {"ref": "texto_padrao"}}
        )

        # Nenhum projeto foi informado — só cliente/programa, como acontece na
        # tela de gerar relatório antes do usuário escolher o projeto.
        nivel = scan_required_nivel(template_json, cliente=cli, programa=prog)
        self.assertEqual(nivel, "projeto")


class TemplateNivelExigidoViewTest(TestCase):
    """GET /templates/<id>/nivel-exigido/ — front-end consulta esse endpoint
    em vez de reimplementar scan_required_nivel no cliente."""

    def _doc(self, *blocos):
        return {"type": "doc", "content": list(blocos)}

    def _par(self, *inline):
        return {"type": "paragraph", "content": list(inline)}

    def _txt(self, texto):
        return {"type": "text", "text": texto}

    def _var_text(self, ref):
        return {"type": "var_text", "attrs": {"ref": ref}}

    def setUp(self):
        self.client_api = APIClient()
        self.user_admin = User.objects.create_user(
            email="admin_nivel@test.com", password="pass", full_name="Admin"
        )
        MembroGeRelat.objects.create(user=self.user_admin)
        self.client_api.force_authenticate(user=self.user_admin)

        self.cliente = Cliente.objects.create(
            nome="Brisa",
            cnpj="33333333333333",
            nome_contato="C3",
            email_contato="c3@c.com",
            fone_contato="3333",
            numero_contrato="103",
            data_termino_contrato="2030-01-01",
        )
        self.programa = Programa.objects.create(nome="TIC57", cliente=self.cliente)

        CampoDefinicao.objects.create(
            programa=self.programa,
            nivel_aplicacao=NivelAplicacao.PROJETO,
            referencia="nome_escola",
            descricao="Escola atendida pelo projeto",
            tipo=CampoTipo.TEXT,
        )
        cd_texto = CampoDefinicao.objects.create(
            programa=self.programa,
            nivel_aplicacao=NivelAplicacao.PROGRAMA,
            referencia="texto_padrao",
            descricao="Parágrafo padrão do relatório",
            tipo=CampoTipo.RICHTEXT,
        )
        CampoValor.objects.create(
            definicao=cd_texto,
            programa=self.programa,
            valor=self._doc(
                self._par(
                    self._txt("Atividade realizada na escola "),
                    self._var_text("nome_escola"),
                    self._txt("."),
                )
            ),
        )

        self.template = Template.objects.create(
            nome="Relatório Programa",
            programa=self.programa,
            nivel=NivelTemplate.PROGRAMA,
            modelo_json=self._doc(
                {"type": "var_richtext", "attrs": {"ref": "texto_padrao"}}
            ),
        )

    def test_nivel_exigido_reflete_dependencia_transitiva_do_texto_rico(self):
        res = self.client_api.get(
            f"/templates/{self.template.id}/nivel-exigido/",
            {"programa_id": self.programa.id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nivel_exigido"], "projeto")

    def test_nivel_exigido_null_quando_nao_ha_dependencia_de_nivel(self):
        template_simples = Template.objects.create(
            nome="Relatório Simples",
            programa=self.programa,
            nivel=NivelTemplate.PROGRAMA,
            modelo_json=self._doc(self._par(self._txt("Sem variáveis."))),
        )
        res = self.client_api.get(
            f"/templates/{template_simples.id}/nivel-exigido/",
            {"programa_id": self.programa.id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["nivel_exigido"])


class CabecalhoLogosTest(TestCase):
    """Cabeçalho de página do .docx com as logomarcas do cliente e da parceira
    (document_engine.renderer + document_engine.variables)."""

    @staticmethod
    def _png_bytes(size, cor) -> bytes:
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", size, cor).save(buf, "PNG")
        return buf.getvalue()

    def _asset(self, size=(16, 16), cor="red"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return Asset.objects.create(
            arquivo=SimpleUploadedFile(
                "logo.png",
                self._png_bytes(size, cor),
                content_type="image/png",
            ),
            cliente=self.cli,
        )

    @staticmethod
    def _abrir_docx(buf):
        from io import BytesIO

        from docx import Document

        return Document(BytesIO(buf.getvalue()))

    @staticmethod
    def _imagens_no_cabecalho(doc) -> int:
        header = doc.sections[0].header
        return sum(1 for r in header.part.rels.values() if "image" in r.reltype)

    def setUp(self):
        import tempfile

        from django.test import override_settings

        self._media = tempfile.mkdtemp()
        cm = override_settings(MEDIA_ROOT=self._media)
        cm.enable()
        self.addCleanup(cm.disable)

        self.cli = Cliente.objects.create(
            nome="Cliente Logo",
            cnpj="11111111111111",
            nome_contato="C",
            email_contato="c@c.com",
            fone_contato="1",
            numero_contrato="1",
            data_termino_contrato="2030-01-01",
        )
        self.prog = Programa.objects.create(nome="Prog", cliente=self.cli)
        self.proj = Projeto.objects.create(nome="Proj", programa=self.prog)

    _DOC = {"type": "doc", "content": [{"type": "paragraph", "content": []}]}

    # ── renderer ─────────────────────────────────────────────────

    def test_sem_logos_nao_cria_cabecalho(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        doc = self._abrir_docx(prosemirror_to_docx(self._DOC))
        self.assertEqual(len(doc.sections[0].header.tables), 0)
        self.assertEqual(self._imagens_no_cabecalho(doc), 0)

    def test_duas_logos_no_cabecalho(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        a1 = self._asset(size=(16, 16), cor="red")
        a2 = self._asset(size=(24, 12), cor="blue")
        doc = self._abrir_docx(
            prosemirror_to_docx(
                self._DOC, logo_cliente_id=a1.id, logo_parceira_id=a2.id
            )
        )
        self.assertEqual(len(doc.sections[0].header.tables), 1)
        self.assertEqual(self._imagens_no_cabecalho(doc), 2)

    def test_so_cliente_uma_logo(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        a1 = self._asset()
        doc = self._abrir_docx(
            prosemirror_to_docx(self._DOC, logo_cliente_id=a1.id, logo_parceira_id=None)
        )
        self.assertEqual(len(doc.sections[0].header.tables), 1)
        self.assertEqual(self._imagens_no_cabecalho(doc), 1)

    def test_asset_id_invalido_nao_quebra(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        doc = self._abrir_docx(
            prosemirror_to_docx(
                self._DOC, logo_cliente_id=999999, logo_parceira_id=None
            )
        )
        self.assertEqual(len(doc.sections[0].header.tables), 0)

    # ── variables / metadados ────────────────────────────────────

    def test_build_variables_context_congela_asset_ids(self):
        from apps.gerelat.document_engine.variables import build_variables_context

        logo = self._asset()
        self.cli.logomarca = logo
        self.cli.save()
        logo_proj = self._asset()
        self.proj.logomarca = logo_proj
        self.proj.save()

        ctx = build_variables_context(projeto_id=self.proj.id)
        self.cli.refresh_from_db()
        self.proj.refresh_from_db()
        self.assertEqual(
            ctx["sistema.cabecalho.logo_cliente_asset_id"], self.cli.logomarca_id
        )
        self.assertEqual(
            ctx["sistema.cabecalho.logo_parceira_asset_id"], self.proj.logomarca_id
        )

    def test_context_sem_projeto_parceira_none(self):
        from apps.gerelat.document_engine.variables import build_variables_context

        ctx = build_variables_context(cliente_id=self.cli.id)
        self.assertIsNone(ctx["sistema.cabecalho.logo_parceira_asset_id"])

    def test_geracao_grava_asset_ids_em_metadados(self):
        from apps.gerelat.tasks import _do_generate_relatorio

        logo = self._asset()
        self.cli.logomarca = logo
        self.cli.save()

        template = Template.objects.create(
            programa=self.prog,
            nivel=NivelTemplate.PROGRAMA,
            nome="T",
            modelo_json=self._DOC,
        )
        resultado = _do_generate_relatorio(
            projeto_id=self.proj.id,
            programa_id=self.prog.id,
            template_id=template.id,
        )
        rel = Relatorio.objects.get(id=resultado["id"])
        self.cli.refresh_from_db()
        self.assertEqual(
            rel.metadados["sistema.cabecalho.logo_cliente_asset_id"],
            self.cli.logomarca_id,
        )


class AssinaturasRelatorioTest(TestCase):
    """Bloco de assinaturas ao final do .docx (document_engine.renderer) +
    resolução dos signatários (services.assinaturas_relatorio) + congelamento em
    Relatorio.metadados."""

    _DOC = {"type": "doc", "content": [{"type": "paragraph", "content": []}]}

    @staticmethod
    def _abrir_docx(buf):
        from io import BytesIO

        from docx import Document

        return Document(BytesIO(buf.getvalue()))

    def setUp(self):
        self.cli = Cliente.objects.create(
            nome="Cli",
            cnpj="11111111111111",
            nome_contato="c",
            email_contato="c@c.com",
            fone_contato="1",
            numero_contrato="1",
            data_termino_contrato="2030-01-01",
        )
        self.prog = Programa.objects.create(nome="Prog", cliente=self.cli)
        self.proj = Projeto.objects.create(nome="Proj", programa=self.prog)
        self.eq_prog = EquipePrograma.objects.create(
            programa=self.prog, nome="João da Silva", cargo="Coordenador"
        )
        self.eq_proj = EquipeProjeto.objects.create(
            projeto=self.proj,
            nome_equipe="Comissão",
            nome="Maria Souza",
            cargo="Diretora",
        )
        self.template = Template.objects.create(
            projeto=self.proj,
            nivel=NivelTemplate.PROJETO,
            nome="T",
            modelo_json=self._DOC,
        )

    # ── renderer ─────────────────────────────────────────────────

    def test_render_assinaturas_no_fim(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        doc = self._abrir_docx(
            prosemirror_to_docx(
                self._DOC,
                assinaturas=[
                    {
                        "nome": "João da Silva",
                        "cargo": "Coordenador",
                        "nome_equipe": "",
                    },
                    {
                        "nome": "Maria Souza",
                        "cargo": "Diretora",
                        "nome_equipe": "Comissão",
                    },
                ],
            )
        )
        textos = [p.text for p in doc.paragraphs]
        blob = "\n".join(textos)
        self.assertIn("_" * 40, blob)
        self.assertIn("João da Silva", blob)
        self.assertIn("Coordenador", blob)
        self.assertIn("Maria Souza", blob)
        self.assertIn("Comissão", blob)
        # duas linhas de assinatura
        self.assertEqual(textos.count("_" * 40), 2)

    def test_sem_assinaturas_nao_gera_linha(self):
        from apps.gerelat.document_engine.renderer import prosemirror_to_docx

        doc = self._abrir_docx(prosemirror_to_docx(self._DOC))
        self.assertNotIn("_" * 40, "\n".join(p.text for p in doc.paragraphs))

    # ── resolver_assinaturas ─────────────────────────────────────

    def test_resolver_do_template(self):
        from apps.gerelat.services.assinaturas_relatorio import resolver_assinaturas

        AssinaturaTemplate.objects.create(
            template=self.template, equipe_programa=self.eq_prog
        )
        AssinaturaTemplate.objects.create(
            template=self.template, equipe_projeto=self.eq_proj
        )
        linhas = resolver_assinaturas(self.template.id)
        self.assertEqual(
            linhas,
            [
                {"nome": "João da Silva", "cargo": "Coordenador", "nome_equipe": ""},
                {
                    "nome": "Maria Souza",
                    "cargo": "Diretora",
                    "nome_equipe": "Comissão",
                },
            ],
        )

    def test_resolver_com_override(self):
        from apps.gerelat.services.assinaturas_relatorio import resolver_assinaturas

        AssinaturaTemplate.objects.create(
            template=self.template, equipe_programa=self.eq_prog
        )
        linhas = resolver_assinaturas(
            self.template.id,
            assinaturas_override=[{"equipe_projeto": self.eq_proj.id}],
        )
        self.assertEqual([linha["nome"] for linha in linhas], ["Maria Souza"])

    # ── geração / metadados ──────────────────────────────────────

    def test_geracao_congela_assinaturas(self):
        from apps.gerelat.tasks import _do_generate_relatorio

        AssinaturaTemplate.objects.create(
            template=self.template, equipe_programa=self.eq_prog
        )
        resultado = _do_generate_relatorio(
            projeto_id=self.proj.id, template_id=self.template.id
        )
        rel = Relatorio.objects.get(id=resultado["id"])
        self.assertEqual(
            rel.metadados["sistema.assinaturas"],
            [{"nome": "João da Silva", "cargo": "Coordenador", "nome_equipe": ""}],
        )

    # ── serializer ───────────────────────────────────────────────

    def test_serializer_rejeita_duas_equipes(self):
        from apps.gerelat.serializers import RelatorioGenerateRequestSerializer

        s = RelatorioGenerateRequestSerializer(
            data={
                "template": self.template.id,
                "projeto": self.proj.id,
                "assinaturas": [
                    {
                        "equipe_programa": self.eq_prog.id,
                        "equipe_projeto": self.eq_proj.id,
                    }
                ],
            }
        )
        self.assertFalse(s.is_valid())
        self.assertIn("assinaturas", s.errors)

    def test_serializer_rejeita_equipe_de_outro_cliente(self):
        from apps.gerelat.serializers import RelatorioGenerateRequestSerializer

        outro_cli = Cliente.objects.create(
            nome="Outro",
            cnpj="22222222222222",
            nome_contato="o",
            email_contato="o@o.com",
            fone_contato="2",
            numero_contrato="2",
            data_termino_contrato="2030-01-01",
        )
        outro_prog = Programa.objects.create(nome="OutroP", cliente=outro_cli)
        eq_estranha = EquipePrograma.objects.create(
            programa=outro_prog, nome="Fulano", cargo="X"
        )
        s = RelatorioGenerateRequestSerializer(
            data={
                "template": self.template.id,
                "projeto": self.proj.id,
                "assinaturas": [{"equipe_programa": eq_estranha.id}],
            }
        )
        self.assertFalse(s.is_valid())

    # ── regressão do on_delete (2.5) ─────────────────────────────

    def test_excluir_membro_com_assinatura_nao_estoura(self):
        AssinaturaTemplate.objects.create(
            template=self.template, equipe_programa=self.eq_prog
        )
        self.eq_prog.delete()
        self.assertFalse(
            AssinaturaTemplate.objects.filter(template=self.template).exists()
        )
