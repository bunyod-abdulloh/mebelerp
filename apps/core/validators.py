from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE_MB = 5


def validate_image_size(file):
    if file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Rasm hajmi {MAX_IMAGE_SIZE_MB} MB dan oshmasligi kerak.")


MAX_DOCUMENT_SIZE_MB = 10


def validate_document_size(file):
    if file.size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Fayl hajmi {MAX_DOCUMENT_SIZE_MB} MB dan oshmasligi kerak.")
