from django.db import models


class Programa(models.Model):
    id_programa = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    lei_criacao = models.CharField(max_length=150)
    convenio_dados = models.CharField(max_length=150)
    logomarca = models.CharField(max_length=255, blank=True, default="")
    rodape = models.TextField(blank=True, default="")

    def __str__(self):
        return self.nome


class ProgramaCampo(models.Model):
    id_campo = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="campos_programa"
    )
    referencia = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50)
    obrigatorio = models.BooleanField(default=False)
    valor = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.programa.nome} - {self.referencia}"


class EquipePrograma(models.Model):
    id_equipe_programa = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="equipe_programa"
    )
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nome} ({self.cargo})"


class Projeto(models.Model):
    id_projeto = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="projetos"
    )
    nome = models.CharField(max_length=150)
    parceira = models.CharField(max_length=150, blank=True, default="")
    sigla = models.CharField(max_length=30, blank=True, default="")
    logomarca = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.nome


class ProjetoCampo(models.Model):
    id_campo = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="campos_projeto"
    )
    referencia = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50)
    obrigatorio = models.BooleanField(default=False)
    valor = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.projeto.nome} - {self.referencia}"


class EquipeProjeto(models.Model):
    id_equipe_projeto = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="equipes_projeto"
    )
    nome_equipe = models.CharField(max_length=150)
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nome_equipe} - {self.nome} ({self.cargo})"


class ClasseEvento(models.Model):
    id_classe = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="classes_evento"
    )
    nome_classe = models.CharField(max_length=150)

    def __str__(self):
        return self.nome_classe


class Evento(models.Model):
    id_evento = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="eventos"
    )
    classe_evento = models.ForeignKey(
        ClasseEvento, on_delete=models.CASCADE, related_name="eventos"
    )
    nome = models.CharField(max_length=150)
    local = models.CharField(max_length=150, blank=True, default="")
    endereco = models.CharField(max_length=255, blank=True, default="")
    data = models.DateField()
    objetivo = models.TextField(blank=True, default="")

    def __str__(self):
        return self.nome


class Template(models.Model):
    id_template = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="templates",
        null=False,
        blank=False,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    nome_template = models.CharField(max_length=150)
    modelo_arquivo_base = models.CharField(max_length=255)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome_template


class TemplateClasseEvento(models.Model):
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="template_classe_evento"
    )
    classe_evento = models.ForeignKey(
        ClasseEvento,
        on_delete=models.CASCADE,
        related_name="template_classe_evento",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "classe_evento"],
                name="unique_template_classe_evento",
            )
        ]

    def __str__(self):
        return f"{self.template.nome_template} - {self.classe_evento.nome_classe}"


class Relatorio(models.Model):
    id_relatorio = models.AutoField(primary_key=True)
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="relatorios"
    )
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="relatorios"
    )
    arquivo_gerado = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    metadados = models.JSONField(default=dict, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Relatorio {self.id_relatorio} - {self.status}"
