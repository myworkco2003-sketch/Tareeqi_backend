"""Translate normalized communication rows into the map's public API format."""
from .models import CommunicationInfo


def sector_label(sector):
    return {'public': 'قطاع عام / حكومي', 'private': 'قطاع خاص', 'joint': 'قطاع مشترك'}.get(sector.lower(), sector)


def serialize_contact(place):
    contact = dict.fromkeys(('phone', 'mobile', 'short_number', 'whatsapp', 'email', 'website'), '')
    contact.update(social_media={}, opening_hours=place.opening_hours)
    for row in place.communication_info.all():
        key = row.type
        if key == 'phone' and row.value.isdigit() and len(row.value) <= 5:
            key = 'short_number'
        if key in contact and key not in ('social_media', 'opening_hours'):
            if not contact[key]:
                contact[key] = row.value
        else:
            contact['social_media'].setdefault(key, row.value)
    return contact


def save_contact_values(place, **values):
    social = values.pop('social_media', {})
    values.update({key.lower(): value for key, value in social.items()})
    for kind, value in values.items():
        if value:
            CommunicationInfo.objects.get_or_create(
                place=place, type='phone' if kind == 'short_number' else kind, value=value,
            )
