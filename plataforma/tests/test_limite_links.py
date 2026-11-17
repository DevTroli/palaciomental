from django.contrib.auth import get_user_model
from django.test import TestCase

from plataforma.forms import ProjectLinkFormSet
from plataforma.models import Project, ProjectLink


class LimiteLinksTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="autor")
        self.project = Project.objects.create(owner=owner, title="Projeto", direction="Contexto")

    def dados(self, quantidade):
        data = {"links-TOTAL_FORMS": str(quantidade), "links-INITIAL_FORMS": "0"}
        for i in range(quantidade):
            data.update({f"links-{i}-label": f"Link {i}", f"links-{i}-url": f"https://example.com/{i}"})
        return data

    def test_aceita_seis_e_recusa_sete(self):
        self.assertTrue(ProjectLinkFormSet(self.dados(6), instance=self.project, prefix="links").is_valid())
        formset = ProjectLinkFormSet(self.dados(7), instance=self.project, prefix="links")
        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_permite_substituir_link_no_limite(self):
        links = [ProjectLink.objects.create(project=self.project, label=str(i), url=f"https://example.com/{i}") for i in range(6)]
        data = self.dados(7)
        data["links-INITIAL_FORMS"] = "6"
        for i, link in enumerate(links):
            data[f"links-{i}-id"] = str(link.pk)
        data["links-0-DELETE"] = "on"
        formset = ProjectLinkFormSet(data, instance=self.project, prefix="links")
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(self.project.links.count(), 6)
        self.assertFalse(self.project.links.filter(pk=links[0].pk).exists())
