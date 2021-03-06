from django.conf.urls import patterns, url
from mapentity.registry import MapEntityOptions

from .views import JSSettings, admin_check_extents, DocumentPublic, DocumentPublicPDF


urlpatterns = patterns(
    '',
    url(r'^api/settings.json', JSSettings.as_view(), name='settings_json'),
    url(r'^tools/extents/', admin_check_extents, name='check_extents'),
)


class PublishableEntityOptions(MapEntityOptions):
    document_public_view = DocumentPublic
    document_public_pdf_view = DocumentPublicPDF

    def scan_views(self, *args, **kwargs):
        """ Adds the URLs of all views provided by ``PublishableMixin`` models.
        """
        views = super(PublishableEntityOptions, self).scan_views(*args, **kwargs)
        publishable_views = patterns(
            '',
            url(r'^document/print-%s-(?P<pk>\d+).odt$' % self.modelname,
                self.document_public_view.as_view(model=self.model),
                name="%s_document_public" % self.modelname),
            url(r'^api/{name}/{name}-(?P<pk>\d+).pdf$'.format(name=self.modelname),
                self.document_public_pdf_view.as_view(model=self.model),
                name="%s_printable" % self.modelname),
        )
        return publishable_views + views
