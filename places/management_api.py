"""Session-authenticated place management, using the existing tables."""
import math
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from rest_framework import serializers, generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Place, Category, SubCategory, AdminArea, CommunicationInfo, PlaceMedia


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationInfo
        fields = ['type', 'value']


class MediaSerializer(serializers.ModelSerializer):
    file_url = serializers.URLField(max_length=500)

    class Meta:
        model = PlaceMedia
        fields = ['file_url', 'media_type', 'caption', 'is_cover']


class PlaceSerializer(serializers.ModelSerializer):
    sub_category_id = serializers.PrimaryKeyRelatedField(source='sub_category', queryset=SubCategory.objects.all())
    admin_area_id = serializers.PrimaryKeyRelatedField(source='admin_area', queryset=AdminArea.objects.all(), allow_null=True, required=False)
    category_id = serializers.IntegerField(source='sub_category.category_id', read_only=True)
    category_name = serializers.CharField(source='sub_category.category.name_ar', read_only=True)
    sub_category_name = serializers.CharField(source='sub_category.name_ar', read_only=True)
    admin_area_name = serializers.CharField(source='admin_area.name_ar', read_only=True)
    communication_info = ContactSerializer(many=True, required=False)
    media = MediaSerializer(many=True, required=False)
    is_verified = serializers.BooleanField(default=False)

    class Meta:
        model = Place
        fields = ['id', 'title_ar', 'title_en', 'description', 'sector', 'latitude', 'longitude', 'location_text', 'opening_hours', 'is_visible', 'is_verified', 'sub_category_id', 'admin_area_id', 'category_id', 'category_name', 'sub_category_name', 'admin_area_name', 'communication_info', 'media', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        for field in ('latitude', 'longitude'):
            if field in attrs and not math.isfinite(attrs[field]):
                raise serializers.ValidationError({field: 'إحداثيات غير صالحة'})
        if 'opening_hours' in attrs and not isinstance(attrs['opening_hours'], dict):
            raise serializers.ValidationError({'opening_hours': 'يجب أن تكون ساعات العمل كائنًا'})
        candidate = Place() if self.instance is None else Place.objects.get(pk=self.instance.pk)
        for key, value in attrs.items():
            if key not in ('communication_info', 'media'):
                setattr(candidate, key, value)
        try:
            candidate.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        return self._save(None, validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        return self._save(instance, validated_data)

    def _save(self, instance, data):
        contacts = data.pop('communication_info', None)
        media = data.pop('media', None)
        instance = super().create(data) if instance is None else super().update(instance, data)
        for rows, manager, model in ((contacts, instance.communication_info, CommunicationInfo), (media, instance.media, PlaceMedia)):
            if rows is not None:
                manager.all().delete()
                model.objects.bulk_create([model(place=instance, **row) for row in rows])
        return instance


def filtered_places(params, queryset):
    for key, lookup in {'category_id': 'sub_category__category_id', 'subcategory_id': 'sub_category_id', 'admin_area_id': 'admin_area_id'}.items():
        if params.get(key):
            try:
                value = int(params[key])
                if value < 1:
                    raise ValueError
            except ValueError:
                raise serializers.ValidationError({key: 'معرف غير صالح'})
            queryset = queryset.filter(**{lookup: value})
    for key in ('is_visible', 'is_verified'):
        if params.get(key):
            if params[key] not in ('true', 'false'):
                raise serializers.ValidationError({key: 'استخدم true أو false'})
            queryset = queryset.filter(**{key: params[key] == 'true'})
    if params.get('search'):
        term = params['search'].strip()
        queryset = queryset.filter(Q(title_ar__icontains=term) | Q(title_en__icontains=term))
    if params.get('bbox'):
        try:
            west, south, east, north = map(float, params['bbox'].split(','))
            if not all(map(math.isfinite, [west, south, east, north])) or not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                raise ValueError
        except (ValueError, TypeError):
            raise serializers.ValidationError({'bbox': 'حدود غير صالحة'})
        queryset = queryset.filter(longitude__gte=west, longitude__lte=east, latitude__gte=south, latitude__lte=north)
    return queryset


class Pagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        raw = request.query_params.get('page_size')
        if raw is not None:
            try:
                value = int(raw)
                if value < 1:
                    raise ValueError
            except ValueError:
                raise serializers.ValidationError({'page_size': 'حجم الصفحة يجب أن يكون عددًا موجبًا'})
        return super().get_page_size(request)


class PlaceAccess:
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]
    serializer_class = PlaceSerializer

    def get_queryset(self):
        return filtered_places(self.request.query_params, Place.objects.select_related('sub_category__category', 'admin_area').prefetch_related('communication_info', 'media').order_by('id'))


class PlaceList(PlaceAccess, generics.ListCreateAPIView):
    pagination_class = Pagination


class PlaceDetail(PlaceAccess, generics.RetrieveUpdateDestroyAPIView):
    pass


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def metadata(request):
    return Response({'csrf_token': get_token(request), **place_metadata()})


def place_metadata():
    return {
        'categories': [{'id': c.id, 'name_ar': c.name_ar, 'subcategories': [{'id': s.id, 'name_ar': s.name_ar} for s in c.subcategories.all()]} for c in Category.objects.prefetch_related('subcategories')],
        'admin_areas': list(AdminArea.objects.values('id', 'name_ar')),
        'sectors': sorted(set(['Public', 'private', 'joint']) | set(Place.objects.order_by().values_list('sector', flat=True).distinct())),
        'contact_types': list(CommunicationInfo._meta.get_field('type').choices),
    }


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def map_places(request):
    if not request.query_params.get('bbox'):
        raise serializers.ValidationError({'bbox': 'حدود الخريطة مطلوبة'})
    qs = filtered_places(request.query_params, Place.objects.select_related('sub_category__category').order_by('id'))
    rows = list(qs[:5001])
    return Response({'type': 'FeatureCollection', 'truncated': len(rows) > 5000, 'features': [
        {'type': 'Feature', 'id': p.id, 'geometry': {'type': 'Point', 'coordinates': [p.longitude, p.latitude]}, 'properties': {'id': p.id, 'title': p.title_ar, 'color': p.sub_category.effective_color if p.sub_category else '#064239'}} for p in rows[:5000]
    ]})
