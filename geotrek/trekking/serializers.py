import datetime
import json

import gpxpy
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import translation
from django.utils.timezone import utc, make_aware
from django.utils.xmlutils import SimplerXMLGenerator
from rest_framework import serializers as rest_serializers

from mapentity.serializers import GPXSerializer, plain_text

from geotrek.common.serializers import (
    PictogramSerializerMixin, ThemeSerializer,
    TranslatedModelSerializer, PicturesSerializerMixin,
    PublishableSerializerMixin
)
from geotrek.authent import models as authent_models
from geotrek.common.models import CirkwiTag
from geotrek.zoning.serializers import ZoningSerializerMixin
from geotrek.altimetry.serializers import AltimetrySerializerMixin
from geotrek.trekking import models as trekking_models


class TrekGPXSerializer(GPXSerializer):
    def end_object(self, trek):
        super(TrekGPXSerializer, self).end_object(trek)
        for poi in trek.pois.all():
            wpt = gpxpy.gpx.GPXWaypoint(latitude=poi.geom.y,
                                        longitude=poi.geom.x,
                                        elevation=poi.geom.z)
            wpt.name = u"%s: %s" % (poi.type, poi.name)
            wpt.description = poi.description
            self.gpx.waypoints.append(wpt)


class DifficultyLevelSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    label = rest_serializers.Field(source='difficulty')

    class Meta:
        model = trekking_models.DifficultyLevel
        fields = ('id', 'pictogram', 'label')


class RouteSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    label = rest_serializers.Field(source='route')

    class Meta:
        model = trekking_models.Route
        fields = ('id', 'pictogram', 'label')


class NetworkSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    name = rest_serializers.Field(source='network')

    class Meta:
        model = trekking_models.Route
        fields = ('id', 'pictogram', 'name')


class PracticeSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    label = rest_serializers.Field(source='name')

    class Meta:
        model = trekking_models.Practice
        fields = ('id', 'pictogram', 'label')


class AccessibilitySerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    label = rest_serializers.Field(source='name')

    class Meta:
        model = trekking_models.Accessibility
        fields = ('id', 'pictogram', 'label')


class TypeSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    name = rest_serializers.Field(source='name')

    class Meta:
        model = trekking_models.Practice
        fields = ('id', 'pictogram', 'name')


class WebLinkCategorySerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    class Meta:
        model = trekking_models.WebLinkCategory
        fields = ('id', 'pictogram', 'label')


class WebLinkSerializer(TranslatedModelSerializer):
    category = WebLinkCategorySerializer()

    class Meta:
        model = trekking_models.WebLink
        fields = ('id', 'name', 'category', 'url')


class CloseTrekSerializer(TranslatedModelSerializer):
    category_id = rest_serializers.Field(source='category_id')

    class Meta:
        model = trekking_models.Trek
        fields = ('id', 'category_id')


class RelatedTrekSerializer(TranslatedModelSerializer):
    pk = rest_serializers.Field(source='id')
    slug = rest_serializers.Field(source='slug')
    url = rest_serializers.Field(source='get_detail_url')

    class Meta:
        model = trekking_models.Trek
        fields = ('id', 'pk', 'slug', 'name', 'url')


class TrekRelationshipSerializer(rest_serializers.ModelSerializer):
    published = rest_serializers.Field(source='trek_b.published')
    trek = RelatedTrekSerializer(source='trek_b')

    class Meta:
        model = trekking_models.TrekRelationship
        fields = ('has_common_departure', 'has_common_edge', 'is_circuit_step',
                  'trek', 'published')


class StructureSerializer(rest_serializers.ModelSerializer):
    class Meta:
        model = authent_models.Structure
        fields = ('id', 'name')


class TrekSerializer(PublishableSerializerMixin, PicturesSerializerMixin,
                     AltimetrySerializerMixin, ZoningSerializerMixin,
                     TranslatedModelSerializer):
    duration_pretty = rest_serializers.Field(source='duration_pretty')
    difficulty = DifficultyLevelSerializer()
    route = RouteSerializer()
    networks = NetworkSerializer(many=True)
    themes = ThemeSerializer(many=True)
    practice = PracticeSerializer()
    usages = PracticeSerializer(source='usages', many=True)  # Rando v1 compat
    accessibilities = AccessibilitySerializer(many=True)
    web_links = WebLinkSerializer(many=True)
    relationships = TrekRelationshipSerializer(many=True, source='published_relationships')
    treks = CloseTrekSerializer(many=True, source='published_treks')

    # Idea: use rest-framework-gis
    parking_location = rest_serializers.SerializerMethodField('get_parking_location')
    points_reference = rest_serializers.SerializerMethodField('get_points_reference')

    poi_layer = rest_serializers.SerializerMethodField('get_poi_layer_url')
    information_desk_layer = rest_serializers.SerializerMethodField('get_information_desk_layer_url')
    gpx = rest_serializers.SerializerMethodField('get_gpx_url')
    kml = rest_serializers.SerializerMethodField('get_kml_url')
    structure = StructureSerializer()

    # For consistency with touristic contents
    type1 = TypeSerializer(source='usages', many=True)
    type2 = TypeSerializer(source='accessibilities', many=True)
    category = rest_serializers.SerializerMethodField('get_category')

    def __init__(self, *args, **kwargs):
        super(TrekSerializer, self).__init__(*args, **kwargs)

        from geotrek.tourism import serializers as tourism_serializers

        self.fields['information_desks'] = tourism_serializers.InformationDeskSerializer(many=True)
        self.fields['touristic_contents'] = tourism_serializers.CloseTouristicContentSerializer(many=True, source='published_touristic_contents')
        self.fields['touristic_events'] = tourism_serializers.CloseTouristicEventSerializer(many=True, source='published_touristic_events')

    class Meta:
        model = trekking_models.Trek
        id_field = 'id'  # By default on this model it's topo_object = OneToOneField(parent_link=True)
        geo_field = 'geom'
        fields = ('id', 'departure', 'arrival', 'duration',
                  'duration_pretty', 'description', 'description_teaser',
                  'networks', 'advice', 'ambiance', 'difficulty',
                  'information_desks', 'themes', 'practice', 'accessibilities',
                  'usages', 'access', 'route', 'public_transport', 'advised_parking',
                  'web_links', 'is_park_centered', 'disabled_infrastructure',
                  'parking_location', 'relationships', 'points_reference',
                  'poi_layer', 'information_desk_layer', 'gpx', 'kml',
                  'type1', 'type2', 'category', 'structure', 'treks') + \
            AltimetrySerializerMixin.Meta.fields + \
            ZoningSerializerMixin.Meta.fields + \
            PublishableSerializerMixin.Meta.fields + \
            PicturesSerializerMixin.Meta.fields

    def get_parking_location(self, obj):
        if not obj.parking_location:
            return None
        return obj.parking_location.transform(settings.API_SRID, clone=True).coords

    def get_points_reference(self, obj):
        if not obj.points_reference:
            return None
        geojson = obj.points_reference.transform(settings.API_SRID, clone=True).geojson
        return json.loads(geojson)

    def get_poi_layer_url(self, obj):
        return reverse('trekking:trek_poi_geojson', kwargs={'pk': obj.pk})

    def get_information_desk_layer_url(self, obj):
        return reverse('trekking:trek_information_desk_geojson', kwargs={'pk': obj.pk})

    def get_gpx_url(self, obj):
        return reverse('trekking:trek_gpx_detail', kwargs={'pk': obj.pk})

    def get_kml_url(self, obj):
        return reverse('trekking:trek_kml_detail', kwargs={'pk': obj.pk})

    def get_category(self, obj):
        return {
            'id': obj.category_id,
            'label': obj._meta.verbose_name,
            'type1_label': obj._meta.get_field('practice').verbose_name,
            'type2_label': obj._meta.get_field('accessibilities').verbose_name,
            'pictogram': '/static/trekking/trek.svg',
        }


class POITypeSerializer(PictogramSerializerMixin, TranslatedModelSerializer):
    class Meta:
        model = trekking_models.POIType
        fields = ('id', 'pictogram', 'label')


class ClosePOISerializer(TranslatedModelSerializer):
    slug = rest_serializers.Field(source='slug')
    type = POITypeSerializer()

    class Meta:
        model = trekking_models.Trek
        fields = ('id', 'slug', 'name', 'type')


class POISerializer(PublishableSerializerMixin, PicturesSerializerMixin,
                    ZoningSerializerMixin, TranslatedModelSerializer):
    type = POITypeSerializer()
    structure = StructureSerializer()

    def __init__(self, *args, **kwargs):
        super(POISerializer, self).__init__(*args, **kwargs)

        from geotrek.tourism import serializers as tourism_serializers

        self.fields['touristic_contents'] = tourism_serializers.CloseTouristicContentSerializer(many=True, source='published_touristic_contents')
        self.fields['touristic_events'] = tourism_serializers.CloseTouristicEventSerializer(many=True, source='published_touristic_events')

    class Meta:
        model = trekking_models.Trek
        id_field = 'id'  # By default on this model it's topo_object = OneToOneField(parent_link=True)
        geo_field = 'geom'
        fields = ('id', 'description', 'type',) + \
            ('min_elevation', 'max_elevation', 'structure') + \
            ZoningSerializerMixin.Meta.fields + \
            PublishableSerializerMixin.Meta.fields + \
            PicturesSerializerMixin.Meta.fields


def timestamp(dt):
    epoch = make_aware(datetime.datetime(1970, 1, 1), utc)
    return str(int((dt - epoch).total_seconds()))


class CirkwiPOISerializer:
    def __init__(self, request, stream):
        self.xml = SimplerXMLGenerator(stream, 'utf8')
        self.request = request
        self.stream = stream

    def serialize_field(self, name, value, attrs={}):
        if not value and not attrs:
            return
        value = unicode(value)
        self.xml.startElement(name, attrs)
        if u'<' in value or u'>' in value or u'&' in value:
            self.stream.write('<![CDATA[%s]]>' % value)
        else:
            self.xml.characters(value)
        self.xml.endElement(name)

    def serialize_medias(self, request, pictures):
        if not pictures:
            return
        self.xml.startElement('medias', {})
        self.xml.startElement('images', {})
        for picture in pictures:
            self.xml.startElement('image', {})
            self.serialize_field('legend', picture['legend'])
            self.serialize_field('url', request.build_absolute_uri(picture['url']))
            self.serialize_field('credit', picture['author'])
            self.xml.endElement('image')
        self.xml.endElement('images')
        self.xml.endElement('medias')

    def serialize_pois(self, pois):
        for poi in pois:
            self.xml.startElement('poi', {
                'date_creation': timestamp(poi.date_insert),
                'date_modification': timestamp(poi.date_update),
                'id_poi': str(poi.pk),
            })
            if poi.type.cirkwi:
                self.xml.startElement('categories', {})
                self.serialize_field('categorie', str(poi.type.cirkwi.eid), {'nom': poi.type.cirkwi.name})
                self.xml.endElement('categories')
            orig_lang = translation.get_language()
            for lang in poi.published_langs:
                translation.activate(lang)
                self.xml.startElement('informations', {'language': lang})
                self.serialize_field('titre', poi.name)
                self.serialize_field('description', plain_text(poi.description))
                self.serialize_medias(self.request, poi.serializable_pictures)
                self.xml.endElement('informations')
            translation.activate(orig_lang)
            self.xml.startElement('adresse', {})
            self.xml.startElement('position', {})
            coords = poi.geom.transform(4326, clone=True).coords
            self.serialize_field('lat', coords[1])
            self.serialize_field('lng', coords[0])
            self.xml.endElement('position')
            self.xml.endElement('adresse')
            self.xml.endElement('poi')

    def serialize(self, pois):
        self.xml.startDocument()
        self.xml.startElement('pois', {'version': '2'})
        self.serialize_pois(pois)
        self.xml.endElement('pois')
        self.xml.endDocument()


class CirkwiTrekSerializer(CirkwiPOISerializer):
    def serialize_additionnal_info(self, trek, name):
        value = getattr(trek, name)
        if not value:
            return
        value = plain_text(value)
        self.xml.startElement('information_complementaire', {})
        self.serialize_field('titre', trek._meta.get_field(name).verbose_name)
        self.serialize_field('description', value)
        self.xml.endElement('information_complementaire')

    def serialize_trace(self, trek):
        self.xml.startElement('trace', {})
        for c in trek.geom.transform(4326, clone=True).coords:
            self.xml.startElement('point', {})
            self.serialize_field('lat', c[1])
            self.serialize_field('lng', c[0])
            self.xml.endElement('point')
        self.xml.endElement('trace')

    def serializable_locomotions(self, trek):
        attrs = {}
        if trek.practice and trek.practice.cirkwi:
            attrs['type'] = trek.practice.cirkwi.name
            attrs['id_locomotion'] = str(trek.practice.cirkwi.eid)
        if trek.difficulty and trek.difficulty.cirkwi_level:
            attrs['difficulte'] = str(trek.difficulty.cirkwi_level)
        if trek.duration:
            attrs['duree'] = str(int(trek.duration * 60))
        if attrs:
            self.xml.startElement('locomotions', {})
            self.serialize_field('locomotion', '', attrs)
            self.xml.endElement('locomotions')

    def serialize_description(self, trek):
        description = trek.description_teaser
        if description and trek.description:
            description += u'\n\n'
            description += trek.description
        if description:
            self.serialize_field('description', plain_text(description))

    def serialize_tags(self, trek):
        self.xml.startElement('tags_publics', {})
        tag_ids = list(trek.themes.values_list('cirkwi_id', flat=True))
        tag_ids += trek.accessibilities.values_list('cirkwi_id', flat=True)
        if trek.difficulty and trek.difficulty.cirkwi_id:
            tag_ids.append(trek.difficulty.cirkwi_id)
        for tag in CirkwiTag.objects.filter(id__in=tag_ids):
            self.serialize_field('tag_public', '', {'id': str(tag.eid), 'nom': tag.name})
        self.xml.endElement('tags_publics')

    # TODO: parking location (POI?), points_reference
    def serialize(self, treks):
        self.xml.startDocument()
        self.xml.startElement('circuits', {'version': '2'})
        for trek in treks:
            self.xml.startElement('circuit', {
                'date_creation': timestamp(trek.date_insert),
                'date_modification': timestamp(trek.date_update),
                'id_circuit': str(trek.pk),
            })
            orig_lang = translation.get_language()
            for lang in trek.published_langs:
                translation.activate(lang)
                self.xml.startElement('informations', {'language': lang})
                self.serialize_field('titre', trek.name)
                self.serialize_description(trek)
                self.serialize_medias(self.request, trek.serializable_pictures)
                self.xml.startElement('informations_complementaires', {})
                self.serialize_additionnal_info(trek, 'departure')
                self.serialize_additionnal_info(trek, 'arrival')
                self.serialize_additionnal_info(trek, 'ambiance')
                self.serialize_additionnal_info(trek, 'access')
                self.serialize_additionnal_info(trek, 'disabled_infrastructure')
                self.serialize_additionnal_info(trek, 'advised_parking')
                self.serialize_additionnal_info(trek, 'public_transport')
                self.serialize_additionnal_info(trek, 'advice')
                self.xml.endElement('informations_complementaires')
                self.serialize_tags(trek)
                self.xml.endElement('informations')
                self.serialize_field('distance', int(trek.length))
                self.serializable_locomotions(trek)
            translation.activate(orig_lang)
            self.serialize_trace(trek)
            if trek.published_pois:
                self.xml.startElement('pois', {})
                self.serialize_pois(trek.published_pois.transform(4326, field_name='geom'))
                self.xml.endElement('pois')
            self.xml.endElement('circuit')
        self.xml.endElement('circuits')
        self.xml.endDocument()
