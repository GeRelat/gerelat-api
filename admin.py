import os
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from .utils import gerar_relatorio_docx
from .models import (
    ClasseEvento,
    EquipePrograma,
    EquipeProjeto,
    Evento,
    Programa,
    ProgramaCampo,
    Projeto,
    ProjetoCampo,
    Relatorio,
    Template,
    TemplateClasseEvento,
    AuditLog,
)

# ---- Inlines ---=-----=--------------------------------=

class ProgramaCampoInline(admin.TabularInline):
    model  = ProgramaCampo
    extra  = 1

class EquipeProgramaInline(admin.TabularInline):
    model  = EquipePrograma
    extra  = 1

class ProjetoCampoInline(admin.TabularInline):
    model  = ProjetoCampo
    extra  = 1

class EquipeProjetoInline(admin.TabularInline):
    model  = EquipeProjeto
    extra  = 1

# ---- Admins ----=-----=-------------------------------=

@admin.action(description='Gerar arquivo .DOCX para os itens selecionados')
def exportar_para_docx(modeladmin, request, queryset):
    sucessos = 0
    erros = 0
    pasta_destino = os.path.join(settings.BASE_DIR, 'media', 'relatorios_gerados')
    os.makedirs(pasta_destino, exist_ok=True)
    
    for relatorio in queryset:
        try:
            nome_arquivo = f"Relatorio_{relatorio.id_relatorio}.docx"
            caminho_completo = os.path.join(pasta_destino, nome_arquivo)
            
            gerar_relatorio_docx(relatorio, caminho_completo)

            relatorio.arquivo_gerado = nome_arquivo
            relatorio.status = "Concluido"
            relatorio.save()
            
            sucessos += 1
        except Exception as e:
            erros += 1
            identificador = getattr(relatorio, 'id_relatorio', 'Desconhecido')
            print(f"Erro ao gerar DOCX para o Relatório ID {identificador}: {e}")

    if sucessos > 0:
        modeladmin.message_user(
            request, 
            f"{sucessos} relatório(s) DOCX gerado(s) com sucesso na pasta 'media/relatorios_gerados'!", 
            level=messages.SUCCESS
        )
    if erros > 0:
        modeladmin.message_user(
            request, 
            f"Falha ao gerar {erros} documento(s). Verifique o console.",
            level=messages.ERROR
        )
@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display  = ('id_programa', 'nome', 'lei_criacao', 'logomarca')
    search_fields = ('nome', 'lei_criacao', 'convenio_dados')
    inlines       = [ProgramaCampoInline, EquipeProgramaInline]

#@admin.register(ProgramaCampo)
#class ProgramaCampoAdmin(admin.ModelAdmin):
 #   list_display  = ('id_campo', 'programa', 'referencia', 'tipo', 'obrigatorio')
  #  list_editable = ('obrigatorio',)
   # list_filter   = ('tipo', 'obrigatorio', 'programa')
    #search_fields = ('referencia', 'descricao')

@admin.register(EquipePrograma)
class EquipeProgramaAdmin(admin.ModelAdmin):
    list_display  = ('id_equipe_programa', 'programa', 'nome', 'cargo')
    search_fields = ('nome', 'cargo')
    list_filter   = ('programa',)

@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display        = ('id_projeto', 'nome', 'programa', 'parceira', 'sigla')
    search_fields       = ('nome', 'parceira', 'sigla')
    list_filter         = ('programa',)
    inlines             = [ProjetoCampoInline, EquipeProjetoInline]
    autocomplete_fields = ['programa'] 

@admin.register(ProjetoCampo)
class ProjetoCampoAdmin(admin.ModelAdmin):
    list_display  = ('id_campo', 'projeto', 'referencia', 'tipo', 'obrigatorio')
    list_filter   = ('tipo', 'obrigatorio', 'projeto')
    search_fields = ('referencia', 'descricao')

@admin.register(EquipeProjeto)
class EquipeProjetoAdmin(admin.ModelAdmin):
    list_display  = ('id_equipe_projeto', 'projeto', 'nome_equipe', 'nome', 'cargo')
    search_fields = ('nome', 'nome_equipe', 'cargo')
    list_filter   = ('projeto',)

@admin.register(ClasseEvento)
class ClasseEventoAdmin(admin.ModelAdmin):
    list_display  = ('id_classe', 'nome_classe', 'programa')
    search_fields = ('nome_classe',)
    list_filter   = ('programa',)

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display  = ('id_evento', 'nome', 'projeto', 'classe_evento', 'data', 'local')
    list_select_related = ('projeto', 'classe_evento')
    list_filter   = ('data', 'classe_evento', 'projeto')
    search_fields = ('nome', 'local', 'endereco')


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display  = ('id_template', 'nome_template', 'programa', 'projeto', 'data_criacao', 'ultima_atualizacao')
    search_fields = ('nome_template', 'modelo_arquivo_base')
    list_filter   = ('programa', 'projeto')

@admin.register(TemplateClasseEvento)
class TemplateClasseEventoAdmin(admin.ModelAdmin):
    list_display  = ('template', 'classe_evento')
    list_filter   = ('template', 'classe_evento')

@admin.register(Relatorio)
class RelatorioAdmin(admin.ModelAdmin):
    list_display  = ('id_relatorio', 'evento', 'template', 'status', 'data_criacao')
    list_filter   = ('status', 'data_criacao')
    search_fields = ('arquivo_gerado', 'status')

    actions = [exportar_para_docx]

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('acao','endpoint','usuario','data_hora')
    list_filter = ('acao','data_hora')
    search_fields = ('endpoint','usuario__username')

    readonly_fields = ('acao','endpoint','usuario','data_hora')

@admin.register(Relatorio)
class RelatorioAdmin(admin.ModelAdmin):
    list_display = ('id','status','is_deleted')
    list_filter = ('status','is_deleted')